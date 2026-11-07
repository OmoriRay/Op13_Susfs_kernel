// SPDX-License-Identifier: GPL-2.0-only
#include "codec.h"
#define LZ4_STATIC_LINKING_ONLY
#define LZ4_HC_STATIC_LINKING_ONLY
#include "lz4.h"
#include "lz4hc.h"

int op13_codec_init(struct op13_codec *ctx, bool mid)
{
    size_t size;
    if (!ctx) return -EINVAL;
    ctx->state = NULL;
    ctx->mid = mid;
    size = mid ? sizeof(LZ4_streamHC_t) : sizeof(LZ4_stream_t);
    ctx->state = op13_alloc(size);
    if (!ctx->state) return -ENOMEM;
    if ((mid && !LZ4_initStreamHC(ctx->state, size)) ||
        (!mid && !LZ4_initStream(ctx->state, size))) {
        op13_free(ctx->state); ctx->state = NULL;
        return -EINVAL;
    }
    return 0;
}

void op13_codec_destroy(struct op13_codec *ctx)
{
    if (ctx) { op13_free(ctx->state); ctx->state = NULL; }
}

int op13_codec_compress(struct op13_codec *ctx, const unsigned char *src,
                       unsigned int slen, unsigned char *dst, unsigned int *dlen)
{
    unsigned int capacity;
    int size;
    if (!ctx || !ctx->state || !src || !dst || !dlen || slen != PAGE_SIZE)
        return -EINVAL;
    capacity = *dlen < 2 * PAGE_SIZE ? *dlen : 2 * PAGE_SIZE;
    if (!capacity) return -EINVAL;
    if (ctx->mid) {
        /* A fresh independent block: no reference to any earlier swap page. */
        LZ4_resetStreamHC_fast(ctx->state, 2);
        size = LZ4_compress_HC_continue(ctx->state, (const char *)src,
                                      (char *)dst, slen, capacity);
    } else {
        size = LZ4_compress_fast_extState(ctx->state, (const char *)src,
                                         (char *)dst, slen, capacity, 1);
    }
    if (size <= 0) return -EINVAL;
    *dlen = size;
    return 0;
}

int op13_codec_decompress(const unsigned char *src, unsigned int slen,
                         unsigned char *dst, unsigned int *dlen)
{
    int size;
    if (!src || !dst || !dlen || !slen || slen > 2 * PAGE_SIZE || *dlen < PAGE_SIZE)
        return -EINVAL;
    size = LZ4_decompress_safe((const char *)src, (char *)dst, slen, PAGE_SIZE);
    if (size != PAGE_SIZE) return -EINVAL;
    *dlen = size;
    return 0;
}
