#!/usr/bin/python3

# -*- coding: utf-8 -*-

"""Module for HTCondor and XRootD access tokens
   author: Brian Bockelman
"""

import base64
import sys
import time
import uuid

import pymacaroons
import kubernetes

import jwt
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

NAMESPACE = "default"
SITE_LOCATION = "T2_US_Nebraska"
MACAROON_NAME = "cms"
CONDOR_KID = "POOL"
IDENTITY = "bbockelm@unl.edu"
ISSUER = "red-condor.unl.edu"

def escape_username(input_name):
    result = ''
    for character in input_name:
        if character.isalnum():
            result += character
        else:
            result += '-%0x' % ord(character)
    return result

def create_macaroon():
    m = pymacaroons.Macaroon(location=SITE_LOCATION, identifier = str(uuid.uuid4()), key="secret1234")
    m.add_first_party_caveat("name:%s" % MACAROON_NAME)
    m.add_first_party_caveat("activity:DOWNLOAD")
    m.add_first_party_caveat("path:/store")
    m.add_first_party_caveat("before:2020-05-23T20:45:34Z")
    return m.serialize()

def simple_scramble(in_buf):
    """
    Undo the simple scramble of HTCondor - simply
    XOR with 0xdeadbeef
    """
    deadbeef = [0xde, 0xad, 0xbe, 0xef]
    out_buf = b''
    for idx in range(len(in_buf)):
        scramble = in_buf[idx] ^ deadbeef[idx % 4]
        out_buf += b'%c' % scramble
    return out_buf

def derive_master_key(password):
    # Key length, salt, and info fixed as part of protocol
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"htcondor",
        info=b"master jwt",
        backend=default_backend())
    return hkdf.derive(password)

def sign_token(identity, issuer, kid, master_key):
    payload = {'sub': identity,
               'iat': int(time.time()),
               'iss': issuer
              }
    encoded = jwt.encode(payload, master_key, headers={'kid': kid}, algorithm='HS256')
    return encoded

def create_condor_token():
    keyfile = "test.key"
    kid = "POOL"
    with open(keyfile, 'rb') as fp:
        scrambled_password = fp.read()
    password = simple_scramble(scrambled_password)
    if CONDOR_KID == 'POOL':
        password = password + password  # surprise!
    master_key = derive_master_key(password)
    return sign_token(IDENTITY, ISSUER, CONDOR_KID, master_key).decode()

def main():
    username = sys.argv[1]
    kubernetes.config.load_kube_config()
    api = kubernetes.client.CoreV1Api()
    euser = escape_username(username)
    print("Querying k8s for secrets for %s" % euser)
    label = "jhub_user=%s" % euser
    secrets = api.list_namespaced_secret(NAMESPACE, label_selector=label)
    print("Count of secrets: %d" % len(secrets.items))
    if len(secrets.items):
        print("Secret already exists - not overwriting")
        return

    body = kubernetes.client.V1Secret()
    body.data = {}
    macaroon = create_macaroon()
    condor_token = create_condor_token()
    body.data["xcache_token"] = base64.b64encode(macaroon.encode('ascii')).decode('ascii')
    body.data["condor_token"] = base64.b64encode(condor_token.encode('ascii')).decode('ascii')
    body.metadata = kubernetes.client.V1ObjectMeta()
    body.metadata.name = '%s-token' % euser
    body.metadata.labels = {}
    body.metadata.labels['jhub_user'] = euser
    print(body)
    try:
        api.create_namespaced_secret(NAMESPACE, body)
    except kubernetes.client.rest.ApiException as ae:
        if ae.status == 409:
            print("Secret already exists - ignoring")
        else:
            raise

if __name__ == '__main__':
    main()
