import contextlib
import distutils.util
import os, socket

from auth import generate_x509, generate_condor, generate_xcache, generate_servicex

from kubernetes import client

# Various secret management configurations
c.KubeSpawner.namespace = os.environ.get('POD_NAMESPACE', 'default')
K8S_NAMESPACE = os.environ.get('POD_NAMESPACE', 'default')

condor_settings = bool(distutils.util.strtobool(os.environ.get('CONDOR_ENABLED', 'True')))
servicex_settings = bool(distutils.util.strtobool(os.environ.get('SERVICEX_ENABLED', 'True')))

if condor_settings is True:
    condor_secret_name = "condor-token"
    condor_user = 'submituser@submit.condorsub.cmsaf-dev.svc.cluster.local'
    issuer = socket.gethostbyname('condor.cmsaf-dev.svc.cluster.local')
    kid = 'POOL'

xcache_secret_name = 'xcache-token'
xcache_location_name = "T2_US_Nebraska"
xcache_user_name = "cms-jovyan"

if servicex_settings is True:
    servicex_secret_name = 'servicex-token'
    servicex_user = 'cms-jovyan@unl.edu'
    servicex_issuer = 'cmsaf-jh.unl.edu'
    servicex_user_name = "cms-jovyan"

external_dns = False
dask_base_domain = os.environ.get('DASK_BASE_DOMAIN', 'coffea.example.edu')

set_config_if_not_none(c.KubeSpawner, 'gid', 'singleuser.gid')

##############################################################################
def get_dask_params(username, base_domain):
    params = {}

    euser = escape_username(username)

    # Limitation on length of metadata.name is 63 symbols: https://www.rfc-editor.org/rfc/rfc1123
    limit = 63
    params['name'] = ('dask-%s' % euser)[:limit]

    # Hostnames for dask manager and worker
    # Eg. user-40example-2eedu.dask.coffea.casa
    #     user-40example-2eedu.dask-worker.coffea.casa
    params['sched-hostname']  = '%s.dask.%s'        % (euser, base_domain)
    params['worker-hostname'] = '%s.dask-worker.%s' % (euser, base_domain)

    return params

def escape_username(input_name):
    result = ''
    for character in input_name:
        if character.isalnum():
            result += character
        else:
            result += '-%0x' % ord(character)
    return result

def username_to_secretname(username):
    euser = escape_username(username)
    return 'jupyter-%s' % euser

##############################################################################
async def pre_spawn_hook(spawner):

    api = client.CoreV1Api()
    euser = escape_username(spawner.user.name)

    # Detect if there are tokens for this user - if so, add them as volume mounts.
    #spawner.environment["BEARER_TOKEN_FILE"] = "/etc/cmsaf-secrets/xcache_token"
    #c.KubeSpawner.environment["XCACHE_HOST"] = "red-xcache1.unl.edu"
    #spawner.environment["XRD_PLUGINCONFDIR"] = "/opt/conda/etc/xrootd/client.plugins.d/"
    spawner.environment["LD_LIBRARY_PATH"] = "/opt/conda/lib/"

    ##########################################################################
    # Generate secret
    secret_name = username_to_secretname(spawner.user.name)
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=secret_name
        ),
        string_data = {}
    )

    ca_key_bytes, ca_cert_bytes, server_bytes, user_bytes = generate_x509()
    xcache_token = generate_xcache(api, K8S_NAMESPACE, xcache_secret_name, xcache_location_name, xcache_user_name)

    # Required fields
    secret.string_data['xcache_token'] = xcache_token
    secret.string_data['ca.key'] = ca_key_bytes.decode('utf-8')
    secret.string_data['ca.pem'] = ca_cert_bytes.decode('utf-8')
    secret.string_data['hostcert.pem'] = server_bytes.decode('utf-8')
    secret.string_data['usercert.pem'] = user_bytes.decode('utf-8')

    # Optional fields
    if condor_settings is True:
        secret.string_data['condor_token'] = generate_condor(api, K8S_NAMESPACE, condor_secret_name, issuer, condor_user, kid)
    if servicex_settings is True:
        secret.string_data['.servicex'] = generate_servicex(api, K8S_NAMESPACE, servicex_secret_name, servicex_issuer, servicex_user)

    # Set access token (if available)
    auth_state = await spawner.user.get_auth_state()
    if auth_state:
        # Requires config.Authenticator.enable_auth_state: true
        access_token = auth_state.get('access_token', None)
        if access_token:
            secret.string_data['access_token'] = access_token

    try:
        # Create the secret...
        api.create_namespaced_secret(K8S_NAMESPACE, secret)
    except client.exceptions.ApiException as e:
        if e.status == 409: # already exists
            # ... but if it's already there, update it
            api.patch_namespaced_secret(secret_name, K8S_NAMESPACE, secret)
        else:
            raise e
    spawner.log.info('Secret configured for %s' % spawner.user.name)

    ##########################################################################
    # Mount secrets into pod
    spawner.volume_mounts.extend([{"name": "cmsaf-secrets", "mountPath": "/etc/cmsaf-secrets"}])
    # The spawner state is retained across spawn attempts
    # Remove old volume config if present, preventing duplication (and failure)
    spawner.volumes = [v for v in spawner.volumes if not v.get('name', None)=='cmsaf-secrets']
    # Add volume for secrets
    spawner.volumes.extend([{"name": "cmsaf-secrets", "secret": {"secretName": secret_name}}])

    ##########################################################################
    # Create a service to serve the Dask scheduler to the outside world
    dask_params = get_dask_params(spawner.user.name, dask_base_domain)
    service = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=dask_params['name'],
        ),
        spec=client.V1ServiceSpec(
            selector={"jhub_user": euser},
            ports = [
                client.V1ServicePort(port = 8786, target_port = 8786, name = "dask-scheduler"),
                client.V1ServicePort(port = 8788, target_port = 8788, name = "dask-worker"),
            ]
        ),
    )

    # Hub role has create/delete, but no update/patch
    with contextlib.suppress(client.exceptions.ApiException):
        # Delete existing service, ignoring absence
        api.delete_namespaced_service(dask_params['name'], K8S_NAMESPACE)
    # Create service
    api.create_namespaced_service(K8S_NAMESPACE, service)
    spawner.log.info('Dask service configured for %s' % spawner.user.name)

    ##########################################################################
    if external_dns:
        # Add hostname to Traefik for this service
        result = api.read_namespaced_service('traefik', K8S_NAMESPACE)

        try:
            hostnames = result.metadata.annotations['external-dns.alpha.kubernetes.io/hostname'].split(',')
        except KeyError:
            hostnames = []

        host_update = False
        if dask_params['sched-hostname'] not in hostnames:
            hostnames.append(dask_params['sched-hostname'])
            host_update = True
        if dask_params['worker-hostname'] not in hostnames:
            hostnames.append(dask_params['worker-hostname'])
            host_update = True

        if host_update:
            api.patch_namespaced_service('traefik', K8S_NAMESPACE,
                body={'metadata': {'annotations':
                         {'external-dns.alpha.kubernetes.io/hostname': ','.join(sorted(hostnames))}}})

    ##########################################################################
    # Create a IngressRequestTCP with TLS routes to find the Dask instances
    api_crd = client.CustomObjectsApi()
    ingress = {'apiVersion': 'traefik.containo.us/v1alpha1',
               'kind': 'IngressRouteTCP',
               'metadata': {'name': dask_params['name']},
               'spec': {'entryPoints': ['dask', 'daskworker'],
                        'routes': [{'match': 'HostSNI(`%s`)' % dask_params['sched-hostname'],
                                    'services': [{'name': dask_params['name'], 'port': 8786}]},
                                   {'match': 'HostSNI(`%s`)' % dask_params['worker-hostname'],
                                    'services': [{'name': dask_params['name'], 'port': 8788}]}],
                        'tls': {'passthrough': True}}}

    with contextlib.suppress(client.exceptions.ApiException):
        api_crd.delete_namespaced_custom_object(
            'traefik.containo.us', 'v1alpha1',
            K8S_NAMESPACE, 'ingressroutetcps', dask_params['name']
        )
    api_crd.create_namespaced_custom_object(
            'traefik.containo.us', 'v1alpha1', K8S_NAMESPACE, 'ingressroutetcps',
            ingress)
    spawner.log.info('Ingress configured for %s' % spawner.user.name)

##############################################################################
def modify_pod_hook(spawner, pod):

    dask_params = get_dask_params(spawner.user.name, dask_base_domain)

    # Add host IP to the pod envvars (to scheduler and sidecar)
    for container in range(len(pod.spec.containers)):
        pod.spec.containers[container].env.append(
            client.V1EnvVar("HOST_IP", dask_params['sched-hostname'])
        )
        pod.spec.containers[container].env.append(
            client.V1EnvVar("WORKER_IP", dask_params['worker-hostname'])
        )

    return pod

##############################################################################
def post_stop_hook(spawner):
    api = client.CoreV1Api()
    api_crd = client.CustomObjectsApi()

    secret_name = username_to_secretname(spawner.user.name)
    dask_params = get_dask_params(spawner.user.name, dask_base_domain)

    with contextlib.suppress(client.exceptions.ApiException):
        #api.delete_namespaced_secret(secret_name, K8S_NAMESPACE)
        api.delete_namespaced_service(dask_params['name'], K8S_NAMESPACE)
        api_crd.delete_namespaced_custom_object(
            'traefik.containo.us', 'v1alpha1',
            K8S_NAMESPACE, 'ingressroutetcps', dask_params['name']
        )

c.KubeSpawner.pre_spawn_hook = pre_spawn_hook
c.KubeSpawner.modify_pod_hook = modify_pod_hook
c.KubeSpawner.post_stop_hook = post_stop_hook
