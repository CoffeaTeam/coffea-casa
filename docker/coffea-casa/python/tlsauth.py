#!/usr/bin/python3

# -*- coding: utf-8 -*-

"""Module for generation TLS  credentials for Dask
   author: Nick Smith
"""

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
import datetime


COMMON_SUBJECT_ATTRIB = [
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'coffea'),
    x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, 'Coffea casa'),
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Nebraska'),
    x509.NameAttribute(NameOID.LOCALITY_NAME, 'UNL'),
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


if __name__ == '__main__':
    ca_cert, ca_key = generate_ca(common_name='Coffea farm development CA')
    with open("ca.key", "wb") as f:
        f.write(ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(b'password')
        ))
    with open("ca.crt", "wb") as f:
        f.write(ca_cert.public_bytes(
            encoding=serialization.Encoding.PEM,
        ))

    server_cert, server_key = generate_server_cert(ca_cert, ca_key, common_name='Coffea dask cluster')
    with open("hostcert.pem", "wb") as f:
        f.write(server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
        f.write(server_cert.public_bytes(
            encoding=serialization.Encoding.PEM,
        ))

    user_csr, user_key = generate_csr(common_name='Coffea user')
    user_cert = sign_csr(ca_cert, ca_key, user_csr)
    with open("usercert.pem", "wb") as f:
        f.write(user_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
        f.write(user_cert.public_bytes(
            encoding=serialization.Encoding.PEM,
        ))
