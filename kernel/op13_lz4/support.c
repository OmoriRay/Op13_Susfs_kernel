// SPDX-License-Identifier: GPL-2.0-only
#ifdef OP13_CODEC_HOST_TEST
unsigned long op13_allocations;
void *op13_alloc(size_t size) { op13_allocations++; return calloc(1, size); }
void op13_free(void *pointer) { free(pointer); }
#else
void *op13_alloc(size_t size) { return kvzalloc(size, GFP_KERNEL); }
void op13_free(void *pointer) { kvfree(pointer); }
#endif
void *op13_LZ4_malloc(size_t size) { return op13_alloc(size); }
void *op13_LZ4_calloc(size_t count, size_t size)
{
    if (count && size > (size_t)-1 / count) return NULL;
    return op13_alloc(count * size);
}
void op13_LZ4_free(void *pointer) { op13_free(pointer); }
