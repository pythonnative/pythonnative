import fs from 'node:fs';
import assert from 'node:assert/strict';
import {matches} from '../../src/pythonnative/devserver/static/contracts.js';
const cases = JSON.parse(fs.readFileSync(new URL('../contracts/validation.json', import.meta.url)));
for (const item of cases) assert.equal(matches(item.value, item.schema), item.valid, item.name);
console.log(`${cases.length} browser contract fixtures passed`);
