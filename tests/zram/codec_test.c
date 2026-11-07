// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include "codec.h"
static uint32_t rng = 8750;
static unsigned char byte(void) { rng ^= rng<<13; rng ^= rng>>17; rng ^= rng<<5; return rng; }
static void fill(unsigned char *p, unsigned int i)
{
    for (unsigned int j=0;j<PAGE_SIZE;j++) {
        unsigned char b=byte();
        p[j] = i%5==0 ? b : i%5==1 ? (j%29) : i%5==2 ? (j%32<24 ? 0 : b) :
               i%5==3 ? 0 : (j%64<60 ? (j%11) : b);
    }
}
int main(void)
{
    unsigned char src[PAGE_SIZE], packed[2*PAGE_SIZE], restored[PAGE_SIZE], reference[PAGE_SIZE];
    void *lib=dlopen("liblz4.so.1",RTLD_NOW);
    assert(lib);
    int (*decode)(const char*,char*,int,int)=dlsym(lib,"LZ4_decompress_safe");
    assert(decode);
    unsigned long verified=0, invalid=0, longrun=0;
    for (int mode=0;mode<2;mode++) {
        struct op13_codec ctx;
        assert(op13_codec_init(&ctx,mode)==0);
        unsigned long allocs=op13_allocations;
        for (unsigned int i=0;i<2000;i++) {
            fill(src,i);
            unsigned int n=sizeof(packed), out=sizeof(restored);
            assert(op13_codec_compress(&ctx,src,PAGE_SIZE,packed,&n)==0 && n<=sizeof(packed));
            assert(op13_codec_decompress(packed,n,restored,&out)==0 && out==PAGE_SIZE);
            assert(!memcmp(src,restored,PAGE_SIZE));
            assert(decode((const char*)packed,(char*)reference,n,PAGE_SIZE)==PAGE_SIZE);
            assert(!memcmp(src,reference,PAGE_SIZE));
            verified++;
            out=PAGE_SIZE-1;
            assert(op13_codec_decompress(packed,n,restored,&out)==-EINVAL); invalid++;
            out=0;
            assert(op13_codec_decompress(packed,n,restored,&out)==-EINVAL); invalid++;
            out=sizeof(packed);
            assert(op13_codec_compress(&ctx,src,PAGE_SIZE-1,packed,&out)==-EINVAL); invalid++;
            out=1;
            assert(op13_codec_compress(&ctx,src,PAGE_SIZE,packed,&out)==-EINVAL); invalid++;
        }
        /* Reuse long enough to exercise HC reset/index maintenance. */
        fill(src,4);
        for (unsigned int i=0;i<100000;i++) {
            src[i%PAGE_SIZE]=(unsigned char)i;
            unsigned int n=sizeof(packed), out=PAGE_SIZE;
            assert(op13_codec_compress(&ctx,src,PAGE_SIZE,packed,&n)==0);
            assert(op13_codec_decompress(packed,n,restored,&out)==0);
            assert(!memcmp(src,restored,PAGE_SIZE)); longrun++;
        }
        assert(op13_allocations==allocs); /* No allocations in per-page paths. */
        op13_codec_destroy(&ctx);
        assert(!ctx.state);
    }
    for (unsigned int i=0;i<10000;i++) {
        unsigned int n=1+(i%sizeof(packed)), out=PAGE_SIZE;
        for (unsigned int j=0;j<n;j++) packed[j]=byte();
        /* Malformed LZ4 can also decode successfully; only memory safety and
         * full-page length are checked, not nonexistent checksum protection. */
        int rc=op13_codec_decompress(packed,n,restored,&out);
        assert(rc==-EINVAL || (rc==0 && out==PAGE_SIZE)); invalid++;
    }
    dlclose(lib);
    printf("{\"varied_roundtrips\":%lu,\"independent_decoder_checks\":%lu,"
           "\"state_reuse_roundtrips\":%lu,\"invalid_boundary_cases\":%lu,"
           "\"hot_path_allocations\":0}\n",verified,verified,longrun,invalid);
    return 0;
}
