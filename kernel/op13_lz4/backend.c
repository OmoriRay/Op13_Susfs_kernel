// SPDX-License-Identifier: GPL-2.0-only
#include <linux/crypto.h>
#include <linux/init.h>
#include <linux/module.h>
#include <crypto/algapi.h>
#include "codec.h"

static int fast_init(struct crypto_tfm *tfm)
{ return op13_codec_init(crypto_tfm_ctx(tfm), false); }
static int mid_init(struct crypto_tfm *tfm)
{ return op13_codec_init(crypto_tfm_ctx(tfm), true); }
static void codec_exit(struct crypto_tfm *tfm)
{ op13_codec_destroy(crypto_tfm_ctx(tfm)); }
static int compress(struct crypto_tfm *tfm, const u8 *src, unsigned int slen,
                    u8 *dst, unsigned int *dlen)
{ return op13_codec_compress(crypto_tfm_ctx(tfm), src, slen, dst, dlen); }
static int decompress(struct crypto_tfm *tfm, const u8 *src, unsigned int slen,
                      u8 *dst, unsigned int *dlen)
{ return op13_codec_decompress(src, slen, dst, dlen); }

#define ALGORITHM(name, initfn) { \
    .cra_name = name, .cra_driver_name = name "-generic", \
    .cra_flags = CRYPTO_ALG_TYPE_COMPRESS, .cra_ctxsize = sizeof(struct op13_codec), \
    .cra_module = THIS_MODULE, .cra_init = initfn, .cra_exit = codec_exit, \
    .cra_u = { .compress = { .coa_compress = compress, .coa_decompress = decompress } } }
static struct crypto_alg algorithms[] = {
    ALGORITHM("lz4-op13", fast_init), ALGORITHM("lz4mid-op13", mid_init)
};
static int __init op13_init(void)
{ return crypto_register_algs(algorithms, ARRAY_SIZE(algorithms)); }
static void __exit op13_exit(void)
{ crypto_unregister_algs(algorithms, ARRAY_SIZE(algorithms)); }
module_init(op13_init);
module_exit(op13_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("OP13 4KB LZ4 1.10.0 fast and MID2 experimental backends");
MODULE_ALIAS_CRYPTO("lz4-op13");
MODULE_ALIAS_CRYPTO("lz4mid-op13");
