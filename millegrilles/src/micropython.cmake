# Librarie crypto Oryx Embedded
# https://www.oryx-embedded.com/
set(ORYX_LIB /home/mathieu/git/millegrilles.rpipico/oryx-embedded)

add_library(usermod_oryx_lib STATIC)

target_sources(usermod_oryx_lib PUBLIC
    ${ORYX_LIB}/common/cpu_endian.c
    ${ORYX_LIB}/common/debug.c
    # ${ORYX_LIB}/common/os_port_none.c
    ${CMAKE_CURRENT_LIST_DIR}/os_port_rpipico.c
    ${ORYX_LIB}/common/date_time.c

    # hash
    ${ORYX_LIB}/cyclone_crypto/hash/blake2s.c
    ${ORYX_LIB}/cyclone_crypto/hash/blake2s256.c
    ${ORYX_LIB}/cyclone_crypto/hash/blake2b.c
    ${ORYX_LIB}/cyclone_crypto/hash/blake2b512.c
    ${ORYX_LIB}/cyclone_crypto/hash/sha1.c
    ${ORYX_LIB}/cyclone_crypto/hash/sha512.c

    # ecc
    ${ORYX_LIB}/cyclone_crypto/ecc/curve25519.c
    ${ORYX_LIB}/cyclone_crypto/ecc/ec.c
    ${ORYX_LIB}/cyclone_crypto/ecc/ecdh.c
    ${ORYX_LIB}/cyclone_crypto/ecc/ec_curves.c
    ${ORYX_LIB}/cyclone_crypto/ecc/ed25519.c
    ${ORYX_LIB}/cyclone_crypto/ecc/eddsa.c
    ${ORYX_LIB}/cyclone_crypto/ecc/x25519.c

    # encoding
    ${ORYX_LIB}/cyclone_crypto/encoding/asn1.c
    ${ORYX_LIB}/cyclone_crypto/encoding/base64.c
    ${ORYX_LIB}/cyclone_crypto/encoding/base64url.c
    ${ORYX_LIB}/cyclone_crypto/encoding/oid.c
    ${ORYX_LIB}/cyclone_crypto/encoding/radix64.c

    # mpi
    ${ORYX_LIB}/cyclone_crypto/mpi/mpi.c

    # pkc
    ${ORYX_LIB}/cyclone_crypto/pkc/dh.c
    ${ORYX_LIB}/cyclone_crypto/pkc/dsa.c
    ${ORYX_LIB}/cyclone_crypto/pkc/rsa.c

    # x509
    ${ORYX_LIB}/cyclone_crypto/pkix/pem_export.c
    ${ORYX_LIB}/cyclone_crypto/pkix/pem_import.c
    ${ORYX_LIB}/cyclone_crypto/pkix/pkcs8_key_format.c
    ${ORYX_LIB}/cyclone_crypto/pkix/pkcs8_key_parse.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_cert_parse.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_cert_validate.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_common.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_cert_create.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_csr_create.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_key_format.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_key_parse.c
    ${ORYX_LIB}/cyclone_crypto/pkix/x509_signature.c
)

target_include_directories(usermod_oryx_lib PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}
    ${ORYX_LIB}/common
    ${ORYX_LIB}/cyclone_crypto
)

add_library(usermod_oryx_crypto INTERFACE)

target_sources(usermod_oryx_crypto INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/crypto_config.h
    ${CMAKE_CURRENT_LIST_DIR}/oryx_crypto.c
)

target_include_directories(usermod_oryx_crypto INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
    ${ORYX_LIB}/common
    ${ORYX_LIB}/cyclone_crypto/encoding
    ${ORYX_LIB}/cyclone_crypto/hash
    ${ORYX_LIB}/cyclone_crypto/ecc
    ${ORYX_LIB}/cyclone_crypto/mpi
    ${ORYX_LIB}/cyclone_crypto/pkc
    ${ORYX_LIB}/cyclone_crypto/pkix
)

# Link our INTERFACE library to the usermod target.
# target_link_libraries(usermod usermod_oryx_crypto)
target_link_libraries(
   usermod_oryx_crypto INTERFACE
   usermod_oryx_lib PUBLIC
)

target_link_libraries(
    usermod INTERFACE
    usermod_oryx_crypto
)
