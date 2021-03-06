/*
 * lang.c
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <alloca.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <linux/keyboard.h>
#ifdef NR_KEYS
#undef NR_KEYS
#define NR_KEYS 128
#endif

#include <zlib.h>

#include "linux/kd.h"

#include "isys.h"
#include "lang.h"

int isysSetUnicodeKeymap(void) {
    int console;

#if defined (__s390__) || defined (__s390x__)
    return 0;
#endif
    console = open("/dev/console", O_RDWR);
    if (console < 0)
	return -EACCES;

    /* place keyboard in unicode mode */
    ioctl(console, KDSKBMODE, K_UNICODE);
    close(console);
    return 0;
}

/* the file pointer must be at the beginning of the section already! */
int loadKeymap(gzFile stream) {
    int console;
    int kmap, key;
    struct kbentry entry;
    int keymaps[MAX_NR_KEYMAPS];
    int count = 0;
    unsigned int magic;
    short keymap[NR_KEYS];
    struct stat sb;

#if defined (__s390__) || defined (__s390x__)
    return 0;
#endif
    if (isVioConsole())
        return 0;

    /* assume that if we're already on a pty loading a keymap is silly */
    fstat(0, &sb);
    if (major(sb.st_rdev) == 3 || major(sb.st_rdev) == 136)
	return 0;

    if (gzread(stream, &magic, sizeof(magic)) != sizeof(magic))
	return -EIO;

    if (magic != KMAP_MAGIC) return -EINVAL;

    if (gzread(stream, keymaps, sizeof(keymaps)) != sizeof(keymaps))
	return -EINVAL;

    console = open("/dev/tty0", O_RDWR);
    if (console < 0)
	return -EACCES;

    for (kmap = 0; kmap < MAX_NR_KEYMAPS; kmap++) {
	if (!keymaps[kmap]) continue;

	if (gzread(stream, keymap, sizeof(keymap)) != sizeof(keymap)) {
	    close(console);
	    return -EIO;
	}

	count++;
	for (key = 0; key < NR_KEYS; key++) {
	    entry.kb_index = key;
	    entry.kb_table = kmap;
	    entry.kb_value = keymap[key];
	    if (KTYP(entry.kb_value) != KT_SPEC) {
		if (ioctl(console, KDSKBENT, &entry)) {
		    int ret = errno;
		    close(console);
		    return ret;
		}
	    }
	}
    }
    close(console);
    return 0;
}

int isysLoadKeymap(char * keymap) {
    int num = -1;
    int rc;
    gzFile f;
    struct kmapHeader hdr;
    struct kmapInfo * infoTable;
    char buf[16384]; 			/* I hope this is big enough */
    int i;

    f = gzopen("/etc/keymaps.gz", "r");
    if (!f) return -EACCES;

    if (gzread(f, &hdr, sizeof(hdr)) != sizeof(hdr)) {
	gzclose(f);
	return -EINVAL;
    }

    i = hdr.numEntries * sizeof(*infoTable);
    infoTable = alloca(i);
    if (gzread(f, infoTable, i) != i) {
	gzclose(f);
	return -EIO;
    }

    for (i = 0; i < hdr.numEntries; i++)
	if (!strcmp(infoTable[i].name, keymap)) {
	    num = i;
	    break;
	}

    if (num == -1) {
	gzclose(f);
	return -ENOENT;
    }

    for (i = 0; i < num; i++) {
	if (gzread(f, buf, infoTable[i].size) != infoTable[i].size) {
	    gzclose(f);
	    return -EIO;
	}
    }

    rc = loadKeymap(f);

    gzclose(f);

    return rc;
}
