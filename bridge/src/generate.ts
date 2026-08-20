/** CLI entry: write checked-in registry artifacts. Not a server. */

import { writeGeneratedArtifacts } from "./registry/generate_artifacts.js";

const written = writeGeneratedArtifacts();
process.stdout.write(`wrote ${written.length} artifacts\n${written.join("\n")}\n`);
