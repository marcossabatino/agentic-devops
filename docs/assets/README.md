# Architecture artwork

The overview is an original vector diagram of the target M1 architecture,
with a separate M2 extension and an explicit current-implementation boundary.
Labels follow the repository's English documentation convention.

| File | Use |
| --- | --- |
| [architecture-overview.svg](architecture-overview.svg) | Editable, scalable source image; 2560 × 1780 canvas |
| [architecture-overview.png](architecture-overview.png) | High-resolution presentation image; 5120 × 3560 pixels |
| [render_architecture.py](../../scripts/render_architecture.py) | Reproducible diagram source: layout, labels, paths, and custom icons |

![Agentic DevOps target architecture and numbered workflow](architecture-overview.svg)

## Update and export

Change the labels or layout in the Python source, then run from the repository:

```sh
python3 scripts/render_architecture.py
python3 scripts/render_architecture.py --png
```

SVG generation uses only the Python standard library. PNG export additionally
requires ImageMagick with the librsvg delegate. The reference render used
ImageMagick/librsvg with Open Sans and Montserrat fonts installed. Fallback fonts
are declared in the SVG; install these fonts to reproduce the same typography.
Rendering does not contact external services or modify the application.

The source generator is authoritative: direct SVG edits are possible, but the
next regeneration will overwrite them. Update both image files when changing
the design. The SVG includes an accessible title and description and contains
no scripts, remote fonts, or external image dependencies.

## Reading the image

Solid teal arrows and numbered badges describe the execution flow. Connections
show the initiating component; responses travel back over the same connection.
The purple dashed panel identifies future AWS integration. Namespace outlines
describe the deployed application boundaries. Observability is deployed; M2 remains planned.

The delivery strip is a setup/deployment workflow, not a dependency called by
every diagnosis. The observability strip describes cross-cutting capabilities;
it is not a detailed telemetry routing diagram. The human gate is an annotation
on the API approval flow, not an additional service.

T04–T07 run separate Kubernetes workloads with restricted network paths,
telemetry and validated deployment provenance. The
orders service owns the PostgreSQL transaction containing its simulated effect
and deduplication. Observability releases are deployed; Bedrock remains future work. See the [HLD](../HIGH_LEVEL_DESIGN.md) for detailed flows.

Visual direction follows the user-supplied
[AWS workflow reference](https://d2908q01vomqb2.cloudfront.net/fc074d501302eb2b93e2554793fcaf50b3bf7291/2022/07/25/The-components-of-the-solution-and-the-steps-in-the-workflow.jpg):
light background, grouped environments, component symbols, and numbered steps.
The layout and symbols here are original; symbols are schematic component icons,
not official vendor logos. The reference image is not redistributed in this repository.
