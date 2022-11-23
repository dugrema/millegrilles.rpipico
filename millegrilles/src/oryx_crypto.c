// Include MicroPython API.
#include "py/obj.h"
#include "py/runtime.h"
#include "../../oryx-embedded/cyclone_crypto/hash/blake2s.h"
#include "../../oryx-embedded/cyclone_crypto/hash/blake2b.h"
#include "../../oryx-embedded/cyclone_crypto/ecc/ed25519.h"
#include "../../oryx-embedded/cyclone_crypto/pkix/x509_common.h"

#define DIGEST_BLAKE2S_LEN 32
#define DIGEST_BLAKE2B_LEN 64

const mp_rom_error_text_t LEN_INVALIDE = "len invalide";
const mp_rom_error_text_t OPERATION_INVALIDE = "oper invalide";
const mp_rom_error_text_t SIGNATURE_INVALIDE = "sign invalide";
const mp_rom_error_text_t DATE_INVALIDE = "date invalide";
const mp_rom_error_text_t ERREUR_PAS_X509 = "pas x509CertInfo";

// Blake2s
STATIC mp_obj_t python_blake2sCompute(mp_obj_t message_data_obj) {

    // Prep message
    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(message_data_obj, &message_bufinfo, MP_BUFFER_READ);

    // Calcul digest
    uint8_t digest_out[DIGEST_BLAKE2S_LEN];
    int res = blake2sCompute(0, 0, message_bufinfo.buf, message_bufinfo.len, digest_out, DIGEST_BLAKE2S_LEN);

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
    int res = blake2bCompute(0, 0, message_bufinfo.buf, message_bufinfo.len, digest_out, DIGEST_BLAKE2B_LEN);

    if(res != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, DIGEST_BLAKE2B_LEN));
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

// x509

// Parse PEM certificat
STATIC mp_obj_t python_x509_read_pem_certificate(mp_obj_t pem_obj) {
    mp_buffer_info_t pem_bufinfo;
    mp_get_buffer_raise(pem_obj, &pem_bufinfo, MP_BUFFER_READ);

    uint8_t der[4096];
    size_t output_len = 4096;
    size_t consumed;

    error_t res_import = pemImportCertificate(pem_bufinfo.buf, pem_bufinfo.len, &der, &output_len, &consumed);

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

// Extraire la cle publique de X509CertificateInfo
STATIC mp_obj_t x509CertInfo_end_date(mp_obj_t o_in) {
    if(!mp_obj_is_type(o_in, &x509CertInfo_type)) {
        mp_raise_TypeError(ERREUR_PAS_X509);
    }

    x509CertInfo_obj_t *enveloppe = MP_OBJ_TO_PTR(o_in);
    X509CertificateInfo *certInfo = &enveloppe->info;
    X509TbsCertificate *tbsCert = &certInfo->tbsCert;
    X509Validity *validity = &tbsCert->validity;

    time_t notAfter = convertDateToUnixTime(&validity->notAfter);

    return mp_obj_new_int(notAfter);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(x509CertInfo_end_date_obj, x509CertInfo_end_date);

STATIC mp_obj_t python_x509_certificat_info(mp_obj_t der_obj) {
    mp_buffer_info_t der_bufinfo;
    mp_get_buffer_raise(der_obj, &der_bufinfo, MP_BUFFER_READ);
    X509CertificateInfo certInfo;

    error_t res_parse = x509ParseCertificate(der_bufinfo.buf, der_bufinfo.len, &certInfo);
    if(res_parse != 0) {
        nlr_raise(mp_obj_new_exception_msg(&mp_type_Exception, OPERATION_INVALIDE));
    }

//    X509TbsCertificate *tbsCert = &certInfo.tbsCert;
//    // Extraire la cle publique du certificat
//    X509SubjectPublicKeyInfo *spki = &tbsCert->subjectPublicKeyInfo;
//    X509EcPublicKey *publicKey = &spki->ecPublicKey;
//    return mp_obj_new_bytes(publicKey->q, 32);

    x509CertInfo_obj_t *result = m_new_obj(x509CertInfo_obj_t);
    result->base.type = &x509CertInfo_type;
    result->info = certInfo;
    return MP_OBJ_FROM_PTR(result);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(python_x509_certificat_info_obj, python_x509_certificat_info);

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
    { MP_ROM_QSTR(MP_QSTR_x509readpemcertificate), MP_ROM_PTR(&python_x509_read_pem_certificate_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509validercertificate), MP_ROM_PTR(&python_x509_valider_der_certificate_obj) },

    { MP_OBJ_NEW_QSTR(MP_QSTR_x509CertInfo), (mp_obj_t)&x509CertInfo_type },
    { MP_ROM_QSTR(MP_QSTR_x509certificatinfo), MP_ROM_PTR(&python_x509_certificat_info_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509PublicKey), MP_ROM_PTR(&x509CertInfo_publicKey_obj) },
    { MP_ROM_QSTR(MP_QSTR_x509EndDate), MP_ROM_PTR(&x509CertInfo_end_date_obj) },
};
STATIC MP_DEFINE_CONST_DICT(oryxcrypto_module_globals, oryxcrypto_module_globals_table);

// Define module object.
const mp_obj_module_t oryxcrypto_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&oryxcrypto_module_globals,
};

// Register the module to make it available in Python.
MP_REGISTER_MODULE(MP_QSTR_oryx_crypto, oryxcrypto_user_cmodule);
