#!/usr/bin/env node
// Snapshot Array Box's single-character symbols; Node is only needed to refresh them.
import { writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const arrayBox = resolve(process.argv[2] || fileURLToPath(new URL('../../../array-box', import.meta.url)));
const maps = await import(pathToFileURL(resolve(arrayBox, 'src/keymap.js')));
const references = await import(pathToFileURL(resolve(arrayBox, 'src/keyboard.js')));
const languages = ['apl', 'kap', 'bqn', 'uiua', 'tinyapl'];
const symbols = new Set();

for (const language of languages) {
    const candidates = [
        ...Object.keys(references[`${language}GlyphNames`]),
        ...Object.keys(references[`${language}GlyphDocs`]),
        ...Object.values(maps[`${language}Keymap`] || {}).flatMap(value =>
            typeof value === 'string' ? [value] : Object.values(value)),
        ...Object.values(maps[`${language}Glyphs`] || {}).flat(),
    ];
    for (const glyph of candidates) {
        // ttfx accepts one Unicode character per symbol, including non-BMP letters.
        if (typeof glyph === 'string' && [...glyph].length === 1
                && !/[\s\p{Mark}\p{Control}]/u.test(glyph))
            symbols.add(glyph);
    }
}

const glyphs = [...symbols].sort((a, b) => a.codePointAt(0) - b.codePointAt(0));
await writeFile(new URL('glyphs.json', import.meta.url), JSON.stringify(glyphs, null, 2) + '\n');
console.log(`Saved ${glyphs.length} unique APL, Kap, BQN, Uiua, and TinyAPL glyphs.`);
