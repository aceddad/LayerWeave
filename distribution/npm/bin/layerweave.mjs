#!/usr/bin/env node
import { main } from '../lib/launch.mjs';

try {
  process.exitCode = await main(process.argv.slice(2));
} catch (error) {
  console.error(`LayerWeave: ${error.message}`);
  process.exitCode = 1;
}
