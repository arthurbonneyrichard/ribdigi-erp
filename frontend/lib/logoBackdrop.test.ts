import assert from 'node:assert/strict';
import test from 'node:test';

import { chooseBackdrop, contrast, luminance, type Pixel, type Rgb } from './logoBackdrop';

const px = (rgb: Rgb, alpha = 255): Pixel => ({ rgb, alpha });
const many = (rgb: Rgb, n: number, alpha = 255) => Array.from({ length: n }, () => px(rgb, alpha));
const clear = (n: number) => many([0, 0, 0], n, 0);
const parse = (h: string): Rgb => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as Rgb;

test('a logo with its own solid background keeps that colour', () => {
  const black: Rgb = [0, 0, 0];
  const pick = chooseBackdrop([...many(black, 80), ...many([74, 176, 18], 20)], many(black, 40));
  assert.equal(pick.background, '#000000');
  assert.equal(luminance(parse(pick.text)) > 0.5, true);
});

test('a dark logo on a transparent background gets a light box', () => {
  const pick = chooseBackdrop([...clear(60), ...many([16, 33, 27], 40)], clear(40));
  assert.ok(luminance(parse(pick.background)) > 0.7, pick.background);
  assert.ok(luminance(parse(pick.text)) < 0.1);
});

test('a white logo on a transparent background gets a dark box', () => {
  const pick = chooseBackdrop([...clear(60), ...many([255, 255, 255], 40)], clear(40));
  assert.ok(luminance(parse(pick.background)) < 0.1, pick.background);
});

test('a coloured logo gets the backdrop where most of it reads best', () => {
  const logo: Rgb[] = [[220, 38, 38], [250, 204, 21]];
  const pixels = [...clear(40), ...many(logo[0], 30), ...many(logo[1], 30)];
  const pick = chooseBackdrop(pixels, clear(40));
  const bg = parse(pick.background);
  const worst = Math.min(...logo.map((c) => contrast(c, bg)));
  // At least as good for its weakest colour as plain white or plain black.
  const plain = Math.max(Math.min(...logo.map((c) => contrast(c, [255, 255, 255]))), Math.min(...logo.map((c) => contrast(c, [11, 15, 13]))));
  assert.ok(worst >= plain - 0.5, `${pick.background} ${worst} vs ${plain}`);
});

test('a fully transparent image falls back to black', () => {
  assert.equal(chooseBackdrop(clear(10), clear(10)).background, '#000000');
});
