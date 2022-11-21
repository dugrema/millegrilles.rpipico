// Include MicroPython API.
#include "py/runtime.h"
#include "../../oryx-embedded/cyclone_crypto/hash/blake2s.h"
#include "../../oryx-embedded/cyclone_crypto/hash/blake2b.h"
#include "../../oryx-embedded/cyclone_crypto/ecc/ed25519.h"

// Blake2s
STATIC mp_obj_t python_blake2sCompute(mp_obj_t message_data_obj, mp_obj_t digest_obj) {

    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(message_data_obj, &message_bufinfo, MP_BUFFER_READ);

    mp_buffer_info_t digest_bufinfo;
    mp_get_buffer_raise(digest_obj, &digest_bufinfo, MP_BUFFER_WRITE);

    if(digest_bufinfo.len != 32) return mp_obj_new_int(-1);

    int res = blake2sCompute(0, 0, message_bufinfo.buf, message_bufinfo.len, digest_bufinfo.buf, digest_bufinfo.len);

    return mp_obj_new_int(res);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(python_blake2sCompute_obj, python_blake2sCompute);

// Blake2b
STATIC mp_obj_t python_blake2bCompute(mp_obj_t message_data_obj, mp_obj_t digest_obj) {

    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(message_data_obj, &message_bufinfo, MP_BUFFER_READ);

    mp_buffer_info_t digest_bufinfo;
    mp_get_buffer_raise(digest_obj, &digest_bufinfo, MP_BUFFER_WRITE);

    if(digest_bufinfo.len != 64) return mp_obj_new_int(-1);

    int res = blake2bCompute(0, 0, message_bufinfo.buf, message_bufinfo.len, digest_bufinfo.buf, digest_bufinfo.len);

    return mp_obj_new_int(res);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(python_blake2bCompute_obj, python_blake2bCompute);

// Ed25519

// Calculer cle publique a partir de la cle privee
/* ed25519GeneratePublicKey(const uint8_t *privateKey, uint8_t *publicKey) */
STATIC mp_obj_t python_ed25519GeneratePublickey(mp_obj_t privateKey_obj, mp_obj_t out_publicKey_obj) {

    mp_buffer_info_t private_key_bufinfo;
    mp_get_buffer_raise(privateKey_obj, &private_key_bufinfo, MP_BUFFER_READ);

    mp_buffer_info_t public_key_bufinfo;
    mp_get_buffer_raise(out_publicKey_obj, &public_key_bufinfo, MP_BUFFER_WRITE);

    if(public_key_bufinfo.len != 32) return mp_obj_new_int(-1);

    int res = ed25519GeneratePublicKey(private_key_bufinfo.buf, public_key_bufinfo.buf);

    return mp_obj_new_int(res);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_2(python_ed25519GeneratePublickey_obj, python_ed25519GeneratePublickey);

/*
    ed25519GenerateSignature(const uint8_t *privateKey,
        const uint8_t *publicKey, const void *message, size_t messageLen,
        const void *context, uint8_t contextLen, uint8_t flag, uint8_t *signature)
*/
STATIC mp_obj_t python_ed25519Sign(mp_uint_t n_args, const mp_obj_t *args) {

    if(n_args != 4) return mp_obj_new_int(-5);

    mp_buffer_info_t privatekey_bufinfo;
    mp_get_buffer_raise(args[0], &privatekey_bufinfo, MP_BUFFER_READ);

    if(privatekey_bufinfo.len != 32) return mp_obj_new_int(-4);

    mp_buffer_info_t publicKey_bufinfo;
    mp_get_buffer_raise(args[1], &publicKey_bufinfo, MP_BUFFER_READ);

    if(publicKey_bufinfo.len != 32) return mp_obj_new_int(-3);

    mp_buffer_info_t message_bufinfo;
    mp_get_buffer_raise(args[2], &message_bufinfo, MP_BUFFER_READ);

    mp_buffer_info_t signature_bufinfo;
    mp_get_buffer_raise(args[3], &signature_bufinfo, MP_BUFFER_WRITE);

    if(signature_bufinfo.len != 64) return mp_obj_new_int(-2);

    const uint8_t flag = 0;

    int res = ed25519GenerateSignature(
        privatekey_bufinfo.buf, publicKey_bufinfo.buf,
        message_bufinfo.buf, message_bufinfo.len,
        0, 0, // context
        flag, 
        signature_bufinfo.buf
    );

    return mp_obj_new_int(res);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(python_ed25519Sign_obj, 4, 4, python_ed25519Sign);

/*
error_t ed25519VerifySignature(const uint8_t *publicKey, const void *message,
   size_t messageLen, const void *context, uint8_t contextLen, uint8_t flag,
   const uint8_t *signature);
*/
STATIC mp_obj_t python_ed25519Verify(mp_obj_t publicKey_obj, mp_obj_t signature_obj, mp_obj_t message_obj) {

    mp_buffer_info_t publicKey_bufinfo;
    mp_get_buffer_raise(publicKey_obj, &publicKey_bufinfo, MP_BUFFER_READ);

    if(publicKey_bufinfo.len != 32) return mp_obj_new_int(-3);

    mp_buffer_info_t signature_bufinfo;
    mp_get_buffer_raise(signature_obj, &signature_bufinfo, MP_BUFFER_READ);

    if(signature_bufinfo.len != 64) return mp_obj_new_int(-3);

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

    return mp_obj_new_int(res);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_3(python_ed25519Verify_obj, python_ed25519Verify);

// Define all properties of the module.
// Table entries are key/value pairs of the attribute name (a string)
// and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be
// optimized to word-sized integers by the build system (interned strings).
STATIC const mp_rom_map_elem_t example_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_oryx_crypto) },
    { MP_ROM_QSTR(MP_QSTR_blake2s), MP_ROM_PTR(&python_blake2sCompute_obj) },
    { MP_ROM_QSTR(MP_QSTR_blake2b), MP_ROM_PTR(&python_blake2bCompute_obj) },
    { MP_ROM_QSTR(MP_QSTR_ed25519sign), MP_ROM_PTR(&python_ed25519Sign_obj) },
    { MP_ROM_QSTR(MP_QSTR_ed25519verify), MP_ROM_PTR(&python_ed25519Verify_obj) },
    { MP_ROM_QSTR(MP_QSTR_ed25519generatepubkey), MP_ROM_PTR(&python_ed25519GeneratePublickey_obj) },
};
STATIC MP_DEFINE_CONST_DICT(example_module_globals, example_module_globals_table);

// Define module object.
const mp_obj_module_t example_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&example_module_globals,
};

// Register the module to make it available in Python.
MP_REGISTER_MODULE(MP_QSTR_oryx_crypto, example_user_cmodule);
