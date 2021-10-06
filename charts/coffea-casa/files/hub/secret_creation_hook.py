import base64
import yaml, os

from auth import generate_x509, generate_condor, generate_xcache, generate_servicex

# Various secret management configurations
c.KubeSpawner.namespace = os.environ.get('POD_NAMESPACE', 'default')
K8S_NAMESPACE = os.environ.get('POD_NAMESPACE', 'default')
condor_secret_name = "condor-token"
condor_user = 'cms-jovyan@unl.edu'
issuer = 'red-condor.unl.edu'
kid = 'POOL'

xcache_secret_name = 'xcache-token'
xcache_location_name = "T2_US_Nebraska"
xcache_user_name = "cms-jovyan"

servicex_secret_name = 'servicex-token'
servicex_user = 'cms-jovyan@unl.edu'
servicex_issuer = 'cmsaf-jh.unl.edu'
servicex_user_name = "cms-jovyan"

external_dns = False
dask_base_domain = os.environ('DASK_BASE_DOMAIN')

set_config_if_not_none(c.KubeSpawner, 'gid', 'singleuser.gid')


# Detect if there are tokens for this user - if so, add them as volume mounts.
c.KubeSpawner.environment["BEARER_TOKEN_FILE"] = os.environ["BEARER_TOKEN_FILE"]
c.KubeSpawner.environment["XCACHE_HOST"] = os.environ["XCACHE_HOST"]
c.KubeSpawner.environment["XRD_PLUGINCONFDIR"] = os.environ["XRD_PLUGINCONFDIR"]
c.KubeSpawner.environment["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
# TODO: make mountPath and name parametrisable (cmsaf-secrets and /etc/cmsaf-secrets)
c.KubeSpawner.volume_mounts.extend([{"name": "cmsaf-secrets", "mountPath": "/etc/cmsaf-secrets"}])
c.KubeSpawner.volumes.extend([{"name": "cmsaf-secrets", "secret": {"secretName": "{username}-secrets"}}])

# Just in time generation of the secrets as needed
def escape_username(input_name):
    result = ''
    for character in input_name:
        if character.isalnum():
            result += character
        else:
            result += '-%0x' % ord(character)
    return result


def secret_creation_hook(spawner, pod):

    api = client.CoreV1Api()
    euser = escape_username(spawner.user.name)

    # Create a service to serve the Dask scheduler to the outside world
    label = "jhub_user=%s" % euser
    services = api.list_namespaced_service(K8S_NAMESPACE, label_selector=label)
    if not services.items:
        body = client.V1Service()
        body.metadata = client.V1ObjectMeta()
        body.metadata.name = '%s-dask-service' % euser
        body.metadata.labels = {}
        body.metadata.labels['jhub_user'] = euser
        body.spec = client.V1ServiceSpec()
        body.spec.selector = {"jhub_user": euser}
        port_listing = client.V1ServicePort(port = 8786, target_port = 8786, name = "dask-scheduler")
        worker_port_listing = client.V1ServicePort(port = 8788, target_port = 8788, name = "dask-worker")
        body.spec.ports = [port_listing, worker_port_listing]
        try:
            api.create_namespaced_service(K8S_NAMESPACE, body)
        except client.rest.ApiException as ae:
            if ae.status == 409:
                pass
            else:
                raise

    # Hostnames for dask manager and worker
    # Eg. user-40example-2eedu.dask.coffea.casa
    #     user-40example-2eedu.dask-worker.coffea.casa
    my_hostname = '%s.dask.%s' % (euser, dask_base_domain)
    my_worker_hostname = '%s.dask-worker.%s' % (euser, dask_base_domain)

    if external_dns:
        # Add hostname to Traefik for this service
        result = api.list_namespaced_service("traefik")

        try:
            hostnames = result.items[0].metadata.annotations['external-dns.alpha.kubernetes.io/hostname'].split(',')
        except KeyError:
            hostnames = list()

        host_update = False
        if my_hostname not in hostnames:
            hostnames.append(my_hostname)
            host_update = True
        if my_worker_hostname not in hostnames:
            hostnames.append(my_worker_hostname)
            host_update = True

        if host_update:
            api.patch_namespaced_service('traefik', 'traefik',
                body={'metadata': {'annotations':
                         {'external-dns.alpha.kubernetes.io/hostname': ','.join(hostnames)}}})

    # Now, we want to query for the IngressRequestTCP and add a new TLS route
    # to find the Dask instance
    api_crd = client.CustomObjectsApi()

    result = api_crd.list_namespaced_custom_object("traefik.containo.us", "v1alpha1", K8S_NAMESPACE, "ingressroutetcps")
    if len(result['items']) != 1:
        raise Exception("Expecting exactly one IngressRouteTCP object")

    found_my_route = False
    found_my_worker_route = False
    my_match = "HostSNI(`%s`)" % my_hostname
    my_worker_match = "HostSNI(`%s`)" % my_worker_hostname
    try:
        routes = result['items'][0]['spec']['routes']
    except KeyError:
        routes = list()
    for route in routes:
        if route['match'] == my_match:
            found_my_route = True
        elif route['match'] == my_worker_match:
            found_my_worker_route = True
        if found_my_route and found_my_worker_route:
            break
    patches_to_add = []
    if not found_my_route:
        patches_to_add.append({"op": "add", "path":"/spec/routes/-",
            "value": {"match": my_match, "services": [{"name": "%s-dask-service" % euser, "port": 8786}]}})
    if not found_my_worker_route:
        patches_to_add.append({"op": "add", "path":"/spec/routes/-",
            "value": {"match": my_worker_match, "services": [{"name": "%s-dask-service" % euser, "port": 8788}]}})
    if patches_to_add:
        # Deep magic: we manually override the content-type header so we can append to the list.
        api_crd.api_client.default_headers['Content-Type'] = 'application/json-patch+json'
        result = api_crd.patch_namespaced_custom_object("traefik.containo.us", "v1alpha1", K8S_NAMESPACE, "ingressroutetcps", "ingressroutetcpfoo",
            patches_to_add);
        del api_crd.api_client.default_headers['Content-Type']

    # Add host IP to the pod envvars (to scheduler and sidecar)
    for container in range(len(pod.spec.containers)):
        pod.spec.containers[container].env.append( \
            client.V1EnvVar("HOST_IP", my_hostname)
        )
        pod.spec.containers[container].env.append( \
            client.V1EnvVar("WORKER_IP", my_worker_hostname)
        )

    # Generate secrets as necessary.
    label = "jhub_user=%s" % euser
    secrets = api.list_namespaced_secret(K8S_NAMESPACE, label_selector=label)
    if len(secrets.items):
        print("Secret already exists - not overwriting")
        return pod

    ca_key_bytes, ca_cert_bytes, server_bytes, user_bytes = generate_x509()

    condor_token = generate_condor(api, K8S_NAMESPACE, condor_secret_name, issuer, condor_user, kid)
    xcache_token = generate_xcache(api, K8S_NAMESPACE, xcache_secret_name, xcache_location_name, xcache_user_name)
    servicex_token = generate_servicex(api, K8S_NAMESPACE, servicex_secret_name, servicex_issuer, servicex_user)
    body = client.V1Secret()
    body.data = {}
    body.data["xcache_token"] = base64.b64encode(xcache_token.encode('ascii')).decode('ascii')
    body.data["condor_token"] = base64.b64encode((condor_token + "\n").encode('ascii')).decode('ascii')
    body.data[".servicex"] = base64.b64encode(servicex_token.encode('ascii')).decode('ascii')
    body.data["ca.key"] = base64.b64encode(ca_key_bytes).decode('ascii')
    body.data["ca.pem"] = base64.b64encode(ca_cert_bytes).decode('ascii')
    body.data["hostcert.pem"] = base64.b64encode(server_bytes).decode('ascii')
    body.data["usercert.pem"] = base64.b64encode(user_bytes).decode('ascii')
    body.metadata = client.V1ObjectMeta()
    body.metadata.name = '%s-secrets' % euser
    body.metadata.labels = {}
    body.metadata.labels['jhub_user'] = euser
    try:
        api.create_namespaced_secret(K8S_NAMESPACE, body)
    except client.rest.ApiException as ae:
        if ae.status == 409:
            print("Secret already exists - ignoring")
        else:
            raise
    return pod

c.KubeSpawner.modify_pod_hook = secret_creation_hook
