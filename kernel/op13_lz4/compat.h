/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef OP13_LZ4_COMPAT_H
#define OP13_LZ4_COMPAT_H
#ifdef OP13_CODEC_HOST_TEST
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define PAGE_SIZE 4096
#else
#include <linux/types.h>
#include <linux/limits.h>
#include <linux/string.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/mm.h>
#include <linux/errno.h>
#endif
/* Preallocated extState/stream functions are used in the page path. Heap
 * variants remain out of that path and must never put a 256KB HC state on stack. */
#define LZ4_HEAPMODE 1
#define LZ4HC_HEAPMODE 1
#define LZ4_USER_MEMORY_FUNCTIONS 1
#define LZ4_DEBUG 0
#include "namespace.h"
void *op13_alloc(size_t size);
void op13_free(void *pointer);
#ifdef OP13_CODEC_HOST_TEST
extern unsigned long op13_allocations;
#endif
#endif
