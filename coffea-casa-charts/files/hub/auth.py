import base64
import time
import datetime
import uuid
import yaml

import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

try:
    import pymacaroons
except ModuleNotFoundError:
    pymacaroons = None

COMMON_SUBJECT_ATTRIB = [
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'coffea'),
    x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, 'Coffea farm'),
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Illinois'),
    x509.NameAttribute(NameOID.LOCALITY_NAME, 'Chicago'),
]


def generate_ca(common_name):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)] + COMMON_SUBJECT_ATTRIB)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .not_valid_before(datetime.datetime.today() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.today() + datetime.timedelta(days=365))
        .serial_number(x509.random_serial_number())
        .public_key(private_key.public_key())
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(
            private_key=private_key,
            algorithm=hashes.SHA256(),
            backend=default_backend()
        )
    )
    return certificate, private_key


def generate_server_cert(ca_cert, ca_key, common_name):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)] + COMMON_SUBJECT_ATTRIB)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .not_valid_before(datetime.datetime.today() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.today() + datetime.timedelta(days=365))
        .serial_number(x509.random_serial_number())
        .public_key(private_key.public_key())
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.CLIENT_AUTH,
                ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=True,
        )
        .sign(
            private_key=ca_key,
            algorithm=hashes.SHA256(),
            backend=default_backend()
        )
    )
    return certificate, private_key


def generate_csr(common_name):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)] + COMMON_SUBJECT_ATTRIB)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(name)
        .sign(
            private_key=private_key,
            algorithm=hashes.SHA256(),
            backend=default_backend()
        )
    )
    return csr, private_key


def sign_csr(ca_cert, ca_key, csr):
    if not csr.is_signature_valid:
        raise ValueError("CSR has an invalid signature, not signing!")
    if len(csr.extensions) > 0:
        raise ValueError("CSR has extensions, we forbid this for simplicity")
    cb = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .not_valid_before(datetime.datetime.today() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.today() + datetime.timedelta(days=365))
        .serial_number(x509.random_serial_number())
        .public_key(csr.public_key())
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.CLIENT_AUTH
            ]),
            critical=True,
        )
    )
    # for extension in csr.extensions:
    #     cb = cb.add_extension(extension.value, critical=extension.critical)
    certificate = cb.sign(
        private_key=ca_key,
        algorithm=hashes.SHA256(),
        backend=default_backend()
    )
    return certificate


def generate_x509():
    ca_cert, ca_key = generate_ca(common_name='Coffea farm development CA')
    ca_key_bytes = ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(b'password')
        )
    ca_cert_bytes = ca_cert.public_bytes(
            encoding=serialization.Encoding.PEM,
        )

    server_cert, server_key = generate_server_cert(ca_cert, ca_key, common_name='Coffea dask cluster')
    server_bytes = server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
    server_bytes += server_cert.public_bytes(
            encoding=serialization.Encoding.PEM,
        )

    user_csr, user_key = generate_csr(common_name='Coffea user')
    user_cert = sign_csr(ca_cert, ca_key, user_csr)
    user_bytes = user_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
    user_bytes += user_cert.public_bytes(
            encoding=serialization.Encoding.PEM,
        )

    return ca_key_bytes, ca_cert_bytes, server_bytes, user_bytes

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

def derive_servicex_master_key(password):
    # Key length, salt, and info fixed as part of protocol
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"servicex",
        info=b"master jwt",
        backend=default_backend())
    return hkdf.derive(password)

def sign_token(identity, issuer, kid, master_key):
    payload = {'sub': identity,
               'iat': int(time.time()),
               'jti': uuid.uuid4().hex,
               'iss': issuer
              }
    encoded = jwt.encode(payload, master_key, headers={'kid': kid}, algorithm='HS256')
    return encoded

def sign_servicex_token(identity, issuer, master_key):
    payload = {'sub': identity,
               'iat': int(time.time()),
               'jti': uuid.uuid4().hex,
               'iss': issuer
              }
    encoded = jwt.encode(payload, master_key, algorithm='HS256')
    return encoded

def generate_condor(api, namespace, secret_name, issuer, name, kid):
    secret = api.read_namespaced_secret(secret_name, namespace)
    token_value = base64.b64decode(secret.data["token"])

    password = simple_scramble(token_value)
    if kid == "POOL":
        password += password
    master_key = derive_master_key(password)
    return sign_token(name, issuer, kid, master_key).decode()

def generate_xcache(api, namespace, secret_name, xcache_location, xcache_user_name):
    secret = api.read_namespaced_secret(secret_name, namespace)
    token_value = base64.b64decode(secret.data["token"])

    if not pymacaroons:
        return ""

    m = pymacaroons.Macaroon(location=xcache_location, identifier = str(uuid.uuid4()), key=token_value)
    m.add_first_party_caveat("name:%s" % xcache_user_name)
    m.add_first_party_caveat("activity:DOWNLOAD")
    m.add_first_party_caveat("path:/store")
    dt = datetime.datetime.now()
    datestring = (dt + datetime.timedelta(52*7, 0)).strftime("%FT%TZ")
    m.add_first_party_caveat("before:%s" % datestring)
    return m.serialize()

def generate_servicex(api, namespace, secret_name, issuer, name):
    secret = api.read_namespaced_secret(secret_name, namespace)
    token_value = base64.b64decode(secret.data["token"])
    # let's try the same way it is done for HTCondor
    password = simple_scramble(token_value)
    master_servicex_key = derive_servicex_master_key(password)
    return sign_servicex_token(name, issuer, master_servicex_key).decode()
