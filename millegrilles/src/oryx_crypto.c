// Include MicroPython API.
#include "py/obj.h"
#include "py/runtime.h"
#include "../../oryx-embedded/cyclone_crypto/hash/hash_algorithms.h"
#include "../../oryx-embedded/cyclone_crypto/ecc/ed25519.h"
#include "../../oryx-embedded/cyclone_crypto/ecc/x25519.h"
#include "../../oryx-embedded/cyclone_crypto/ecc/ecdh.h"
#include "../../oryx-embedded/cyclone_crypto/pkix/x509_common.h"
#include "../../oryx-embedded/cyclone_crypto/pkix/x509_cert_parse.h"
#include "../../oryx-embedded/cyclone_crypto/pkix/x509_cert_validate.h"
#include "../../oryx-embedded/cyclone_crypto/pkix/x509_csr_create.h"
#include "../../oryx-embedded/cyclone_crypto/pkix/pem_import.h"
#include "../../oryx-embedded/cyclone_crypto/mac/mac_algorithms.h"
#include "../../oryx-embedded/cyclone_crypto/cipher/cipher_algorithms.h"
#include "../../oryx-embedded/cyclone_crypto/aead/chacha20_poly1305.h"

#define DIGEST_BLAKE2S_LEN 32
#define DIGEST_BLAKE2B_LEN 64
#define X25519_OUTPUT_LEN 32

const mp_rom_error_text_t LEN_INVALIDE = "len invalide";
const mp_rom_error_text_t OPERATION_INVALIDE = "oper invalide";
const mp_rom_error_text_t SIGNATURE_INVALIDE = "sign invalide";
const mp_rom_error_text_t DATE_INVALIDE = "date invalide";
const mp_rom_error_text_t ERREUR_PAS_X509 = "pas x509CertInfo";

// const uint8_t X509_MG_EXTENSION_EXCHANGES[4] = {0x2a, 0x03, 0x04, 0x00};

// Blake2s
STATIC mp_obj_t python_blake2sCompute(mp_obj_t message_data_obj) {
    // Prep message
    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(message_data_obj, &message_bufinfo, MP_BUFFER_READ);

    // Calcul digest
    uint8_t digest_out[DIGEST_BLAKE2S_LEN];
    int res = blake2s256Compute(message_bufinfo.buf, message_bufinfo.len, (uint8_t *)&digest_out);
    if(res != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // Return bytes obj
    return mp_obj_new_bytes(digest_out, DIGEST_BLAKE2S_LEN);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(python_blake2sCompute_obj, python_blake2sCompute);

// Blake2b
STATIC mp_obj_t python_blake2bCompute(mp_obj_t message_data_obj) {

    // Prep message
    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(message_data_obj, &message_bufinfo, MP_BUFFER_READ);

    uint8_t digest_out[DIGEST_BLAKE2B_LEN];
    int res = blake2b512Compute(message_bufinfo.buf, message_bufinfo.len, (uint8_t *)&digest_out);

    if(res != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // Return bytes obj
    return mp_obj_new_bytes(digest_out, DIGEST_BLAKE2B_LEN);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(python_blake2bCompute_obj, python_blake2bCompute);

// Ed25519

// Calculer cle publique a partir de la cle privee
STATIC mp_obj_t python_ed25519GeneratePublickey(mp_obj_t privateKey_obj) {

    // Charger cle privee, valider
    mp_buffer_info_t private_key_bufinfo;
    mp_get_buffer_raise(privateKey_obj, &private_key_bufinfo, MP_BUFFER_READ);
    if(private_key_bufinfo.len != ED25519_PRIVATE_KEY_LEN) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    // Calculer cle publique
    uint8_t cle_publique[ED25519_PUBLIC_KEY_LEN];
    int res = ed25519GeneratePublicKey(private_key_bufinfo.buf, cle_publique);

    if(res != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // Return bytes obj
    return mp_obj_new_bytes(cle_publique, ED25519_PUBLIC_KEY_LEN);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(python_ed25519GeneratePublickey_obj, python_ed25519GeneratePublickey);

/*
    ed25519GenerateSignature(const uint8_t *privateKey,
        const uint8_t *publicKey, const void *message, size_t messageLen,
        const void *context, uint8_t contextLen, uint8_t flag, uint8_t *signature)
*/
STATIC mp_obj_t python_ed25519Sign(mp_obj_t privateKey_obj, mp_obj_t publicKey_obj, mp_obj_t message_obj) {

    // Charger cle privee
    mp_buffer_info_t privatekey_bufinfo;
    mp_get_buffer_raise(privateKey_obj, &privatekey_bufinfo, MP_BUFFER_READ);
    if(privatekey_bufinfo.len != ED25519_PRIVATE_KEY_LEN) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    // Charger cle publique
    mp_buffer_info_t publicKey_bufinfo;
    mp_get_buffer_raise(publicKey_obj, &publicKey_bufinfo, MP_BUFFER_READ);
    if(publicKey_bufinfo.len != ED25519_PUBLIC_KEY_LEN) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    // Charger message
    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(message_obj, &message_bufinfo, MP_BUFFER_READ);

    // Preparer output
    const uint8_t flag = 0;
    uint8_t signature_out[ED25519_SIGNATURE_LEN];

    // Signer
    int res = ed25519GenerateSignature(
        privatekey_bufinfo.buf, publicKey_bufinfo.buf,
        message_bufinfo.buf, message_bufinfo.len,
        0, 0, // context
        flag, 
        signature_out
    );

    if(res != 0) {
        // Erreur de signature
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // Nouveau objet Python bytes avec la signature
    return mp_obj_new_bytes(signature_out, ED25519_SIGNATURE_LEN);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(python_ed25519Sign_obj, python_ed25519Sign);

/*
error_t ed25519VerifySignature(const uint8_t *publicKey, const void *message,
   size_t messageLen, const void *context, uint8_t contextLen, uint8_t flag,
   const uint8_t *signature);
*/
STATIC mp_obj_t python_ed25519Verify(mp_obj_t publicKey_obj, mp_obj_t signature_obj, mp_obj_t message_obj) {

    mp_buffer_info_t publicKey_bufinfo;
    mp_get_buffer_raise(publicKey_obj, &publicKey_bufinfo, MP_BUFFER_READ);

    if(publicKey_bufinfo.len != 32) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    mp_buffer_info_t signature_bufinfo;
    mp_get_buffer_raise(signature_obj, &signature_bufinfo, MP_BUFFER_READ);

    if(signature_bufinfo.len != 64) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(message_obj, &message_bufinfo, MP_BUFFER_READ);

    const uint8_t flag = 0;

    int res = ed25519VerifySignature(
        publicKey_bufinfo.buf,
        message_bufinfo.buf, message_bufinfo.len,
        0, 0, // context
        flag, 
        signature_bufinfo.buf
    );

    if(res != 0) {
        // Erreur de signature
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, SIGNATURE_INVALIDE));
    }

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(python_ed25519Verify_obj, python_ed25519Verify);

// x25519 (chiffrage)

STATIC mp_obj_t python_x25519GeneratePublickey(mp_obj_t privateKey_obj) {
    mp_obj_t result;

    EcdhContext context;
    mp_buffer_info_t private_key_bufinfo;

    //uint8_t da[CURVE25519_BYTE_LEN];  -> private_key_bufinfo.buf
    uint8_t qa[CURVE25519_BYTE_LEN];
    uint8_t g[CURVE25519_BYTE_LEN];

    // Initialiser contexte
    ecdhInit(&context);
    ecLoadDomainParameters(&context.params, &x25519Curve);

    mp_get_buffer_raise(privateKey_obj, &private_key_bufinfo, MP_BUFFER_READ);
    if(private_key_bufinfo.len != CURVE25519_BYTE_LEN) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    //Get the u-coordinate of the base point, put in g
    int error = mpiExport(&context.params.g.x, g, CURVE25519_BYTE_LEN, MPI_FORMAT_LITTLE_ENDIAN);
    if(error != 0) {
        ecdhFree(&context);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // Utiliser private key (da) et point g, calculer public-key (qa)
    error = x25519(qa, (uint8_t*) private_key_bufinfo.buf, g);
    if(error != 0) {
        ecdhFree(&context);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // result = mp_obj_new_bytes(context.qa.q.x, CURVE25519_BYTE_LEN);
    // Retourner qa (public key)
    result = mp_obj_new_bytes(qa, CURVE25519_BYTE_LEN);

    ecdhFree(&context);
    return result;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(python_x25519GeneratePublickey_obj, python_x25519GeneratePublickey);

STATIC mp_obj_t python_x25519ComputeSharedSecret(mp_obj_t privateKey_obj, mp_obj_t peerKey_obj) {
    mp_obj_t result;
    uint8_t output[CURVE25519_BYTE_LEN];
    size_t outputLen;
    mp_buffer_info_t private_key_bufinfo;
    mp_buffer_info_t peer_key_bufinfo;
    EcdhContext context;
    int error;

    // Valider input
    mp_get_buffer_raise(privateKey_obj, &private_key_bufinfo, MP_BUFFER_READ);
    if(private_key_bufinfo.len != CURVE25519_BYTE_LEN) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    mp_get_buffer_raise(peerKey_obj, &peer_key_bufinfo, MP_BUFFER_READ);
    if(peer_key_bufinfo.len != CURVE25519_BYTE_LEN) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_ValueError, LEN_INVALIDE));
    }

    ecdhInit(&context);
    ecLoadDomainParameters(&context.params, &x25519Curve);

    // Importer cles private et peer dans context
    error = mpiImport(&context.da.d, private_key_bufinfo.buf, CURVE25519_BYTE_LEN, MPI_FORMAT_LITTLE_ENDIAN);
    if(error != 0) {
        ecdhFree(&context);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, ERREUR_PAS_X509));
    }

    error = mpiImport(&context.qb.q.x, peer_key_bufinfo.buf, CURVE25519_BYTE_LEN, MPI_FORMAT_LITTLE_ENDIAN);
    if(error != 0) {
        ecdhFree(&context);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, DATE_INVALIDE));
    }

    error = ecdhComputeSharedSecret(&context, (uint8_t *) &output, CURVE25519_BYTE_LEN, &outputLen);

    if(error != 0) {
        ecdhFree(&context);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    result = mp_obj_new_bytes(output, outputLen);
    ecdhFree(&context);

    return result;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(python_x25519ComputeSharedSecret_obj, python_x25519ComputeSharedSecret);


//STATIC mp_obj_t python_x25519(mp_obj_t scalar_obj, mp_obj_t u_cord_obj) {
//    mp_buffer_info_t scalar_bufinfo;
//    mp_buffer_info_t u_cord_bufinfo;
//
//    // Lire buffers input
//    mp_get_buffer_raise(scalar_obj, &scalar_bufinfo, MP_BUFFER_READ);
//    mp_get_buffer_raise(u_cord_obj, &u_cord_bufinfo, MP_BUFFER_READ);
//
//    // Verifier taille des buffers en input
//    if(scalar_bufinfo.len != X25519_OUTPUT_LEN) {
//        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, LEN_INVALIDE));
//    }
//    if(u_cord_bufinfo.len != X25519_OUTPUT_LEN) {
//        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, LEN_INVALIDE));
//    }
//
//    // Effectuer la conversion x25519
//    uint8_t output[X25519_OUTPUT_LEN];
//    int res = x25519((uint8_t *) &output, scalar_bufinfo.buf, u_cord_bufinfo.buf);
//
//    if(res != 0) {
//        // Erreur de signature
//        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
//    }
//
//    // Generer buffer en reponse
//    return mp_obj_new_bytes(output, X25519_OUTPUT_LEN);
//}
//STATIC MP_DEFINE_CONST_FUN_OBJ_2(python_x25519_obj, python_x25519);

// x509

// Parse PEM certificat
STATIC mp_obj_t python_x509_read_pem_certificate(mp_obj_t pem_obj) {
    mp_buffer_info_t pem_bufinfo;
    mp_get_buffer_raise(pem_obj, &pem_bufinfo, MP_BUFFER_READ);

    uint8_t der[4096];
    size_t output_len = 4096;
    size_t consumed;

    error_t res_import = pemImportCertificate((char*)pem_bufinfo.buf, pem_bufinfo.len, der, &output_len, &consumed);

    if(res_import != 0) {
        // Erreur de signature
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    return mp_obj_new_bytes(der, output_len);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(python_x509_read_pem_certificate_obj, python_x509_read_pem_certificate);

// x509 parse
error_t x509_validate_date(const X509CertificateInfo *certInfo, time_t currentTime) {
    DateTime currentDate;
    const X509Validity *validity;

    //Convert Unix timestamp to date
    convertUnixTimeToDate(currentTime, &currentDate);

    //The certificate validity period is the time interval during which the
    //CA warrants that it will maintain information about the status of the
    //certificate
    validity = &certInfo->tbsCert.validity;

    //Check the validity period
    if(compareDateTime(&currentDate, &validity->notBefore) < 0 ||
     compareDateTime(&currentDate, &validity->notAfter) > 0)
    {
        //The certificate has expired or is not yet valid
        return ERROR_CERTIFICATE_EXPIRED;
    }

    return 0;
}

STATIC mp_obj_t python_x509_valider_der_certificate(mp_obj_t der_obj, mp_obj_t parent_der_obj, mp_obj_t validation_time) {
    mp_buffer_info_t der_bufinfo;
    mp_get_buffer_raise(der_obj, &der_bufinfo, MP_BUFFER_READ);
    X509CertificateInfo certInfo;

    mp_buffer_info_t parent_der_bufinfo;
    mp_get_buffer_raise(parent_der_obj, &parent_der_bufinfo, MP_BUFFER_READ);
    X509CertificateInfo parent_certInfo;

    time_t valid_time = mp_obj_get_int(validation_time);

    error_t res_parse = x509ParseCertificate(der_bufinfo.buf, der_bufinfo.len, &certInfo);
    if(res_parse != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    res_parse = x509ParseCertificate(parent_der_bufinfo.buf, parent_der_bufinfo.len, &parent_certInfo);
    if(res_parse != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // Valider le certificat
    error_t res_validation = x509ValidateCertificate(&certInfo, &parent_certInfo, 0);
    if(res_validation != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, SIGNATURE_INVALIDE));
    }

    if(valid_time > 0) {
        error_t cert_date_valid = x509_validate_date(&certInfo, valid_time);
        if(cert_date_valid != 0) {
            nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, DATE_INVALIDE));
        }
        cert_date_valid = x509_validate_date(&parent_certInfo, valid_time);
        if(cert_date_valid != 0) {
            nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, DATE_INVALIDE));
        }
    }

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(python_x509_valider_der_certificate_obj, python_x509_valider_der_certificate);

// Information certificat x509
const mp_obj_type_t x509CertInfo_type;

typedef struct _x509CertInfo_obj_t {
    mp_obj_base_t base;
    X509CertificateInfo info;
} x509CertInfo_obj_t;

const mp_obj_type_t x509CertInfo_type = {
    { &mp_type_type },
    .name = MP_QSTR_x509CertInfo,
    // .print = x509CertInfo_print,
    // .make_new = x509CertInfo_make_new,
};

// x509 extraction

// Extraire la cle publique de X509CertificateInfo
STATIC mp_obj_t x509CertInfo_publicKey(mp_obj_t o_in) {
    if(!mp_obj_is_type(o_in, &x509CertInfo_type)) {
        mp_raise_TypeError(ERREUR_PAS_X509);
    }

    x509CertInfo_obj_t *enveloppe = MP_OBJ_TO_PTR(o_in);
    X509CertificateInfo *certInfo = &enveloppe->info;
    X509TbsCertificate *tbsCert = &certInfo->tbsCert;

    // Extraire la cle publique du certificat
    X509SubjectPublicKeyInfo *spki = &tbsCert->subjectPublicKeyInfo;
    X509EcPublicKey *publicKey = &spki->ecPublicKey;

    return mp_obj_new_bytes(publicKey->q, 32);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(x509CertInfo_publicKey_obj, x509CertInfo_publicKey);

// Extraire date d'expiration de X509CertificateInfo
STATIC mp_obj_t x509CertInfo_end_date(mp_obj_t o_in) {
    if(!mp_obj_is_type(o_in, &x509CertInfo_type)) {
        mp_raise_TypeError(ERREUR_PAS_X509);
    }

    x509CertInfo_obj_t *enveloppe = MP_OBJ_TO_PTR(o_in);
    X509CertificateInfo *certInfo = &enveloppe->info;
    X509TbsCertificate *tbsCert = &certInfo->tbsCert;
    X509Validity *validity = &tbsCert->validity;

    time_t notAfter = convertDateToUnixTime(&validity->notAfter);

    return mp_obj_new_int_from_ll(notAfter);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(x509CertInfo_end_date_obj, x509CertInfo_end_date);

// Extraire roles du certificat
STATIC mp_obj_t x509CertInfo_extension(mp_obj_t o_in, mp_obj_t oid_extension) {
    if(!mp_obj_is_type(o_in, &x509CertInfo_type)) {
        mp_raise_TypeError(ERREUR_PAS_X509);
    }

    // OID de l'extension
    mp_buffer_info_t oid_bufinfo;
    mp_get_buffer_raise(oid_extension, &oid_bufinfo, MP_BUFFER_READ);

    x509CertInfo_obj_t *enveloppe = MP_OBJ_TO_PTR(o_in);
    X509CertificateInfo *certInfo = &enveloppe->info;
    X509TbsCertificate *tbsCert = &certInfo->tbsCert;
    X509Extensions *extensions = &tbsCert->extensions;

    uint_t numExtensions = extensions->numCustomExtensions;
    for(uint_t extNo=0; extNo < numExtensions; extNo++) {
        X509Extension *ext = &extensions->customExtensions[extNo];
        // return mp_obj_new_bytes(ext->oid, ext->oidLen);
        if(ext->oidLen != oid_bufinfo.len) continue;  // Skip, mismatch len
        if(memcmp(ext->oid, oid_bufinfo.buf, ext->oidLen) == 0) {
            return mp_obj_new_str((const char *)ext->value, ext->valueLen);
        }
    }

    return mp_const_none;
    // return mp_obj_new_int(numExtensions);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(x509CertInfo_extension_obj, x509CertInfo_extension);

STATIC mp_obj_t python_x509_certificat_info(mp_obj_t der_obj) {
    mp_buffer_info_t der_bufinfo;
    mp_get_buffer_raise(der_obj, &der_bufinfo, MP_BUFFER_READ);
    X509CertificateInfo certInfo;

    error_t res_parse = x509ParseCertificate(der_bufinfo.buf, der_bufinfo.len, &certInfo);
    if(res_parse != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    x509CertInfo_obj_t *result = m_new_obj(x509CertInfo_obj_t);
    result->base.type = &x509CertInfo_type;
    result->info = certInfo;
    return MP_OBJ_FROM_PTR(result);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(python_x509_certificat_info_obj, python_x509_certificat_info);

STATIC mp_obj_t python_x509_csr_new(mp_obj_t cleprivee_obj, mp_obj_t cn_obj) {
    // Vars
    const char *namedCurve = "Ed22519";
    // const uint8_t *namedCurve = "Ed22519";
    mp_buffer_info_t cleprivee_bufinfo;
    mp_buffer_info_t cn_bufinfo;
    uint8_t cle_publique[ED25519_PUBLIC_KEY_LEN];
    X509SignatureAlgoId signatureAlgoId;
    X509CertRequestInfo certReqInfo;
    error_t error;
    EddsaPrivateKey privateKey;
    EddsaPublicKey publicKey;
    uint8_t output[2048];
    size_t outputLen = 0;

    // Importer params
    mp_get_buffer_raise(cleprivee_obj, &cleprivee_bufinfo, MP_BUFFER_READ);
    if(cleprivee_bufinfo.len != 32) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, LEN_INVALIDE));
    }
    mp_get_buffer_raise(cn_obj, &cn_bufinfo, MP_BUFFER_READ);

    // Calculer la cle publique Ed25519
    if(ed25519GeneratePublicKey(cleprivee_bufinfo.buf, cle_publique) != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // uint8_t oidSignatureEd25519[4];
    signatureAlgoId.oid = ED25519_OID;
    signatureAlgoId.oidLen = sizeof(ED25519_OID);

    // oidFromString(const char_t *str, uint8_t *oid, size_t maxOidLen, size_t *oidLen)
    // oidFromString("1.3.101.112", &oidSignatureEd25519, sizeof(oidSignatureEd25519), &signatureAlgoId.oidLen);

    // return mp_obj_new_bytes(oidSignatureEd25519, signatureAlgoId.oidLen);

    // PrngAlgo prngAlgo;  // Reste vide, pas necessaire pour Ed25519
    // uint8_t prngContext = 1;

    certReqInfo.rawData = NULL;
    certReqInfo.rawDataLen = 0;

    // X509Version version;
    certReqInfo.version = 0x00;

    // X509Name subject;
    certReqInfo.subject.rawData = NULL;
    certReqInfo.subject.rawDataLen = 0;
    certReqInfo.subject.commonName = cn_bufinfo.buf;
    certReqInfo.subject.commonNameLen = cn_bufinfo.len;
    certReqInfo.subject.organizationalUnitNameLen = 0;
    certReqInfo.subject.organizationNameLen = 0;
    certReqInfo.subject.localityNameLen = 0;
    certReqInfo.subject.stateOrProvinceNameLen = 0;
    certReqInfo.subject.countryNameLen = 0;
    certReqInfo.subject.organizationalUnitNameLen = 0;
    certReqInfo.subject.organizationalUnitNameLen = 0;

    // X509SubjectPublicKeyInfo subjectPublicKeyInfo;
    // const uint8_t *rawData;
    certReqInfo.subjectPublicKeyInfo.rawData = NULL;
    // size_t rawDataLen;
    certReqInfo.subjectPublicKeyInfo.rawDataLen = 0;
    // const uint8_t *oid;
    certReqInfo.subjectPublicKeyInfo.oid = ED25519_OID;
    // size_t oidLen;
    certReqInfo.subjectPublicKeyInfo.oidLen = sizeof(ED25519_OID);
    // X509EcParameters ecParams;
    // const uint8_t *namedCurve;
    certReqInfo.subjectPublicKeyInfo.ecParams.namedCurve = (const uint8_t *)namedCurve;
    // size_t namedCurveLen;
    certReqInfo.subjectPublicKeyInfo.ecParams.namedCurveLen = sizeof(*namedCurve);
    // X509EcPublicKey ecPublicKey;
    certReqInfo.subjectPublicKeyInfo.ecPublicKey.q = (uint8_t *) &cle_publique;
    certReqInfo.subjectPublicKeyInfo.ecPublicKey.qLen = sizeof(ED25519_PUBLIC_KEY_LEN);

    // X509Attributes attributes;
    certReqInfo.attributes.rawData = NULL;
    certReqInfo.attributes.rawDataLen = 0;

    // X509ChallengePassword attributes.challengePwd
    certReqInfo.attributes.challengePwd.value = NULL;
    certReqInfo.attributes.challengePwd.length = 0;

    // X509Extensions extensionReq
    // const uint8_t *rawData;
    certReqInfo.attributes.extensionReq.rawData = NULL;
    // size_t rawDataLen;
    certReqInfo.attributes.extensionReq.rawDataLen = 0;

    // X509BasicConstraints basicConstraints;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.basicConstraints.critical = FALSE;
    // bool_t cA;
    certReqInfo.attributes.extensionReq.basicConstraints.cA = FALSE;
    // int_t pathLenConstraint;
    certReqInfo.attributes.extensionReq.basicConstraints.pathLenConstraint = 0;

    // X509NameConstraints nameConstraints;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.nameConstraints.critical = FALSE;
    // const uint8_t *permittedSubtrees;
    certReqInfo.attributes.extensionReq.nameConstraints.permittedSubtrees = NULL;
    // size_t permittedSubtreesLen;
    certReqInfo.attributes.extensionReq.nameConstraints.permittedSubtreesLen = 0;
    // const uint8_t *excludedSubtrees;
    certReqInfo.attributes.extensionReq.nameConstraints.excludedSubtrees = NULL;
    // size_t excludedSubtreesLen;
    certReqInfo.attributes.extensionReq.nameConstraints.excludedSubtreesLen = 0;

    // X509KeyUsage keyUsage;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.keyUsage.critical = FALSE;
    // uint16_t bitmap;
    certReqInfo.attributes.extensionReq.keyUsage.bitmap = 0;

    // X509ExtendedKeyUsage extKeyUsage;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.extKeyUsage.critical = FALSE;
    // uint8_t bitmap;
    certReqInfo.attributes.extensionReq.extKeyUsage.bitmap = 0;

    // X509SubjectAltName subjectAltName;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.subjectAltName.critical = FALSE;
    // const uint8_t *rawData;
    certReqInfo.attributes.extensionReq.subjectAltName.rawData = NULL;
    // size_t rawDataLen;
    certReqInfo.attributes.extensionReq.subjectAltName.rawDataLen = 0;
    // uint_t numGeneralNames;
    certReqInfo.attributes.extensionReq.subjectAltName.numGeneralNames = 0;
    // X509GeneralName generalNames[X509_MAX_SUBJECT_ALT_NAMES];

    // X509SubjectKeyId subjectKeyId;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.subjectKeyId.critical = FALSE;
    // const uint8_t *value;
    certReqInfo.attributes.extensionReq.subjectKeyId.value = NULL;
    // size_t length;
    certReqInfo.attributes.extensionReq.subjectKeyId.length = 0;

    // X509AuthorityKeyId authKeyId;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.authKeyId.critical = FALSE;
    // const uint8_t *keyId;
    certReqInfo.attributes.extensionReq.authKeyId.keyId = NULL;
    // size_t keyIdLen;
    certReqInfo.attributes.extensionReq.authKeyId.keyIdLen = 0;

    // X509NsCertType nsCertType;
    // bool_t critical;
    certReqInfo.attributes.extensionReq.nsCertType.critical = FALSE;
    // uint8_t bitmap;
    certReqInfo.attributes.extensionReq.nsCertType.bitmap = 0;

    // uint_t numCustomExtensions;
    certReqInfo.attributes.extensionReq.numCustomExtensions = 0;

    // Preparer cles publiques et privees
    eddsaInitPublicKey(&publicKey);
    error = mpiImport(&publicKey.q, (uint8_t *)&cle_publique, ED25519_PUBLIC_KEY_LEN, MPI_FORMAT_LITTLE_ENDIAN);
    if(error != 0) {
        // Free mem
        eddsaFreePublicKey(&publicKey);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    eddsaInitPrivateKey(&privateKey);
    error = mpiImport(&privateKey.d, (uint8_t *) cleprivee_bufinfo.buf, ED25519_PRIVATE_KEY_LEN, MPI_FORMAT_LITTLE_ENDIAN);
    if(error != 0) {
        // Free mem
        eddsaFreePrivateKey(&privateKey);
        eddsaFreePublicKey(&publicKey);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    // Generer nouveau CSR
    error = x509CreateCsr(NULL, NULL,
       &certReqInfo, &publicKey,
       &signatureAlgoId, &privateKey,
       (uint8_t *) &output, &outputLen);

    // Free mem
    eddsaFreePrivateKey(&privateKey);
    eddsaFreePublicKey(&publicKey);

    if(error != 0) {
        return mp_obj_new_int(error);
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    return mp_obj_new_bytes(output, outputLen);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(python_x509_csr_new_obj, python_x509_csr_new);

// ChaCha20

// /**
// * @brief Authenticated encryption using ChaCha20Poly1305
// * @param[in] k key
// * @param[in] kLen Length of the key
// * @param[in] n Nonce
// * @param[in] nLen Length of the nonce
// * @param[in] a Additional authenticated data
// * @param[in] aLen Length of the additional data
// * @param[in] p Plaintext to be encrypted
// * @param[out] c Ciphertext resulting from the encryption
// * @param[in] length Total number of data bytes to be encrypted
// * @param[out] t MAC resulting from the encryption process
// * @param[in] tLen Length of the MAC
// * @return Error code
// **/
//error_t chacha20Poly1305Encrypt(const uint8_t *k, size_t kLen,
//   const uint8_t *n, size_t nLen, const uint8_t *a, size_t aLen,
//   const uint8_t *p, uint8_t *c, size_t length, uint8_t *t, size_t tLen)

STATIC mp_obj_t python_chacha20poly1305_encrypt(mp_obj_t key_obj, mp_obj_t nonce_obj, mp_obj_t plaintext_obj) {
    uint8_t tag[16];  // output tag (MAC)
    mp_buffer_info_t key_bufinfo;
    mp_buffer_info_t nonce_bufinfo;
    mp_buffer_info_t plaintext_bufinfo;
    error_t result;

    mp_get_buffer_raise(key_obj, &key_bufinfo, MP_BUFFER_READ);
    if(key_bufinfo.len != 32) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, LEN_INVALIDE));
    }
    mp_get_buffer_raise(nonce_obj, &nonce_bufinfo, MP_BUFFER_READ);
    if(nonce_bufinfo.len != 12) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, LEN_INVALIDE));
    }
    mp_get_buffer_raise(plaintext_obj, &plaintext_bufinfo, MP_BUFFER_READ);

    result = chacha20Poly1305Encrypt(
        key_bufinfo.buf, key_bufinfo.len,
        nonce_bufinfo.buf, nonce_bufinfo.len,
        NULL, 0,  // no authenticated data
        // Reuse plaintext buffer as output (ciphertext has same length)
        plaintext_bufinfo.buf, plaintext_bufinfo.buf, plaintext_bufinfo.len,
        (uint8_t *)&tag, 16
    );

    if(result != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    return mp_obj_new_bytes(tag, 16);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(python_chacha20poly1305_encrypt_obj, python_chacha20poly1305_encrypt);

STATIC mp_obj_t python_chacha20poly1305_decrypt(mp_obj_t key_obj, mp_obj_t nonce_tag_obj, mp_obj_t plaintext_obj) {
    mp_buffer_info_t key_bufinfo;
    mp_buffer_info_t nonce_tag_obj_bufinfo;
    mp_buffer_info_t plaintext_bufinfo;
    error_t result;

    mp_get_buffer_raise(key_obj, &key_bufinfo, MP_BUFFER_READ);
    if(key_bufinfo.len != 32) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, LEN_INVALIDE));
    }
    mp_get_buffer_raise(nonce_tag_obj, &nonce_tag_obj_bufinfo, MP_BUFFER_READ);
    if(nonce_tag_obj_bufinfo.len != 28) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, LEN_INVALIDE));
    }
    mp_get_buffer_raise(plaintext_obj, &plaintext_bufinfo, MP_BUFFER_READ);

    result = chacha20Poly1305Decrypt(
        key_bufinfo.buf, key_bufinfo.len,
        nonce_tag_obj_bufinfo.buf, 12,
        NULL, 0,  // no authenticated data
        // Reuse plaintext buffer as output (ciphertext has same length)
        plaintext_bufinfo.buf, plaintext_bufinfo.buf, plaintext_bufinfo.len,
        nonce_tag_obj_bufinfo.buf+12, 16
    );

    if(result != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

    return mp_const_none;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(python_chacha20poly1305_decrypt_obj, python_chacha20poly1305_decrypt);

// Define all properties of the module.
// Table entries are key/value pairs of the attribute name (a string)
// and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be
// optimized to word-sized integers by the build system (interned strings).
STATIC const mp_rom_map_elem_t oryxcrypto_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_oryx_crypto) },
    { MP_ROM_QSTR(MP_QSTR_blake2s), MP_ROM_PTR(&python_blake2sCompute_obj) },
    { MP_ROM_QSTR(MP_QSTR_blake2b), MP_ROM_PTR(&python_blake2bCompute_obj) },
    { MP_ROM_QSTR(MP_QSTR_ed25519sign), MP_ROM_PTR(&python_ed25519Sign_obj) },
    { MP_ROM_QSTR(MP_QSTR_ed25519verify), MP_ROM_PTR(&python_ed25519Verify_obj) },
    { MP_ROM_QSTR(MP_QSTR_ed25519generatepubkey), MP_ROM_PTR(&python_ed25519GeneratePublickey_obj) },
    { MP_ROM_QSTR(MP_QSTR_x25519generatepubkey), MP_ROM_PTR(&python_x25519GeneratePublickey_obj) },
    { MP_ROM_QSTR(MP_QSTR_x25519computesharedsecret), MP_ROM_PTR(&python_x25519ComputeSharedSecret_obj) },

    { MP_ROM_QSTR(MP_QSTR_x509readpemcertificate), MP_ROM_PTR(&python_x509_read_pem_certificate_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509validercertificate), MP_ROM_PTR(&python_x509_valider_der_certificate_obj) },

    { MP_ROM_QSTR(MP_QSTR_cipherchacha20poly1305encrypt), MP_ROM_PTR(&python_chacha20poly1305_encrypt_obj) },
    { MP_ROM_QSTR(MP_QSTR_cipherchacha20poly1305decrypt), MP_ROM_PTR(&python_chacha20poly1305_decrypt_obj) },

    { MP_OBJ_NEW_QSTR(MP_QSTR_x509CertInfo), (mp_obj_t)&x509CertInfo_type },
    { MP_ROM_QSTR(MP_QSTR_x509certificatinfo), MP_ROM_PTR(&python_x509_certificat_info_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509PublicKey), MP_ROM_PTR(&x509CertInfo_publicKey_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509EndDate), MP_ROM_PTR(&x509CertInfo_end_date_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509Extension), MP_ROM_PTR(&x509CertInfo_extension_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509CsrNew), MP_ROM_PTR(&python_x509_csr_new_obj) },
};
STATIC MP_DEFINE_CONST_DICT(oryxcrypto_module_globals, oryxcrypto_module_globals_table);

// Define module object.
const mp_obj_module_t oryxcrypto_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&oryxcrypto_module_globals,
};

// Register the module to make it available in Python.
MP_REGISTER_MODULE(MP_QSTR_oryx_crypto, oryxcrypto_user_cmodule);
