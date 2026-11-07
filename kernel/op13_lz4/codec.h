/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef OP13_LZ4_CODEC_H
#define OP13_LZ4_CODEC_H
struct op13_codec { void *state; bool mid; };
int op13_codec_init(struct op13_codec *ctx, bool mid);
void op13_codec_destroy(struct op13_codec *ctx);
int op13_codec_compress(struct op13_codec *ctx, const unsigned char *src,
                       unsigned int slen, unsigned char *dst, unsigned int *dlen);
int op13_codec_decompress(const unsigned char *src, unsigned int slen,
                         unsigned char *dst, unsigned int *dlen);
#endif
