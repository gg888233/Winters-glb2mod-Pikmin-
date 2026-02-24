GLB → Pikmin MOD Converter

A template-based GLB to .mod converter for Pikmin (GameCube).
This tool rebuilds mesh data using an original .mod file as a structural template while replacing geometry with a custom GLB mesh.

The original file provides the skeleton, chunk layout, and binary structure. The converter injects new vertex data into that framework.

Requirements

Python 3.x

Required Python packages:

pip install pygltflib numpy

Standard library modules used:

struct

argparse

pathlib

Blender is required for preparing and exporting the GLB model.

Usage

Basic command structure:

python .\glb2mod_yel_rigid_packets_FIXED.py -t <BASE_MOD> -g <INPUT_GLB> --axis x_neg_90 --rot 90,0,0 -o <OUTPUT_MOD>

Example:

python .\glb2mod_yel_rigid_packets_FIXED.py -t .\yelModel.mod -g .\YlwRender96.glb --axis x_neg_90 --rot 90,0,0 -o .\out_yel.mod
Orientation Flags (Mandatory)

After exporting your mod file, rename it to whichever mod file you want to replace in the game, put it in the folder where the old MOD file was, and then rebuild the ISO.

The following flags are required:

--axis x_neg_90
--rot 90,0,0

If these are omitted, the model will be incorrectly oriented in-game.

These parameters correct the coordinate system mismatch between Blender (glTF) and Pikmin’s internal coordinate space. They are not optional.

Standard Workflow

Copy the original .mod you want to replace into your working directory.

Export your edited model from Blender as .glb.

Run the converter with the required orientation flags.

Replace the in-game .mod or use Dolphin file replacement at the exact path.

If the game continues loading the original model, you likely replaced the wrong file or a duplicate copy inside an archive.

Blender Procedure (Critical)

This converter depends entirely on preserving the original armature.

You must use the exact same armature as the original model.

Do not:

Rename bones

Delete bones

Add bones

Change hierarchy

Change rest pose significantly

Your custom mesh must be skinned to the original skeleton.

Recommended procedure:

Import or reconstruct the original armature.

Attach your custom mesh to the original armature.

Use weight transfer from the original mesh where possible.

Ensure vertex groups match original bone names exactly.

Export as glTF Binary (.glb).

Do not rely on export axis settings; orientation is handled by the converter.

If you create a new rig or modify the bone structure, the model may crash, deform incorrectly, or be rejected by the engine.

Limitations

This tool does not rebuild skeleton logic. It injects geometry into an existing structure.

Large changes to:

Vertex count

Skinning structure

Bone references

Attribute layout

may cause rendering errors or crashes.

Materials in GLB are preview-only. Pikmin does not use glTF PBR shading. Texture handling is defined by the game’s original material system.

If enemies revert to their original models, the issue is almost always:

Replacing the wrong .mod

Multiple LOD copies

Archive-packed resources not repacked

Cave vs overworld asset duplication

How the Converter Works

The converter:

Parses GLB mesh data

Extracts positions, normals, UVs

Applies axis and rotation transforms

Rebuilds mesh packets (0x0050)

Preserves skeleton, envelope, and structural chunks

Writes a binary-compatible .mod

The original .mod acts as a binary template.

FOR MODDERS / SCRIPTERS

Below are consolidated technical notes gathered during reverse engineering.

Core Relevant MOD Chunks

0x0010 – Vertex Positions
Contains position array. Big-endian floats. Patched in-place.

0x0011 – Normals
Palette-style array. Usually fixed count in base file. Patched in-place.

0x0040 – Vertex Matrix Table
Appears to map vertex indices to joint references. Often ends with negative sentinel values.

0x0041 – Matrix Envelope / Weights
Stores weight information for skinned vertices.
Important discovery: verify if weights are float32 (check for 3F 80 00 00 = 1.0 big-endian).
Do not assume 16-bit fixed without checking.

0x0050 – Mesh Chunk (Core Geometry)

Structure summary:

32-bit BE: submesh count

32-bit BE: always zero

Submesh descriptors:

16-bit counts and offsets for positions, normals, colors, UVs

Followed by:

Display list / strip stream

Skinning references (indices into 0x0040 / 0x0041)

Critical constraint:
Payload size must remain consistent unless rebuilding entire layout.
Safer approach: preserve chunk length and rebuild internal packet data carefully.

0x0060 – Bounds
Contains bounding box. Often patchable at payload+0x20 region.

Important Reverse Engineering Conclusions

Always verify endianness. Pikmin uses big-endian.

Confirm weight format before rewriting 0x0041.

Determine whether 0x0050 references:

Direct joint IDs

Indices into 0x0040

Indices into envelope tables

Test by inspecting a single vertex strip and tracing its reference values.

Black Screen Causes

Incorrect payload size for 0x0050

Misaligned packet stream

Invalid envelope index

Bone count mismatch

Reordered or renamed bones

Invalid bounds data

Incorrect float packing (endianness error)

Safe Strategy

Use original .mod as template.

Do not alter chunk sizes unless fully rebuilding format.

Patch geometry in-place where possible.

Preserve skeleton and envelope data untouched.

Keep vertex attribute layout consistent with original.