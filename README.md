# pycar

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Description

`pycar` is a Python package designed to facilitate the conversion of files and folders into Content Addressable Archive (CARv1) files. Inspired by [js-car](https://github.com/ipld/js-car?tab=readme-ov-file#readme). The CAR format (Content Addressable aRchives) can be used to store content addressable objects in the form of IPLD block data as a sequence of bytes, typically in a file with a .car filename extension.

The CAR format serves as a serialized representation of any IPLD DAG (graph) as the concatenation of its blocks, plus a header that describes the graphs in the file via root CIDs. While the requirement for the blocks in a CAR to form coherent DAGs is not strict, the CAR format may also be used to store arbitrary IPLD blocks.

In addition to the binary block data, storage overhead for the CAR format includes a header block encoded as DAG-CBOR containing the format version and an array of root CIDs, along with a CID for each block preceding its binary data. Moreover, a compressed integer prefixes each block (including the header block), indicating the total length of that block, including the length of the encoded CID.

The `pycar` package provides a simple yet powerful API for creating CARv1 files from local file systems. Users can choose the chunk size and the number of children per node to customize the conversion process according to their requirements.

For more information about the CARv1 specification, please refer to [CARv1 Specification](https://ipld.io/specs/codecs/car/).

### Features
- Converts files and folders into CARv1 archives.
- Supports configurable chunking for large files.
- Utilizes Protobufs for defining DAG nodes and UnixFS data.
- Generates CIDs (Content IDs) for each block using multihash.
- Implements UnixFS data format for enhanced metadata storage.

### How it Works
pycar utilizes a combination of Protobuf definitions, multihashing algorithms, and UnixFS data structures to create CARv1 files. It recursively traverses the file system, chunking large files as necessary, and constructing a Directed Acyclic Graph (DAG) representing the file and folder hierarchy. Each node in the DAG contains metadata such as file names, sizes, and CIDs of linked data blocks. Finally, the package serializes the DAG into a CARv1 file format, ready for storage or transmission.


#### Video Demo: https://www.youtube.com/watch?v=bz316x4HyRU

#### Helpful links:
[CARv1 Specifications](https://ipld.io/specs/transport/car/carv1/) </br>
[IPLD Tools](https://ipld.io/tools/)

## Installation
```bash
git clone https://github.com/RiteshSaha8145/pycar.git

pip install -e pycar
```

## Usage

### Converting Folders to CARv1 Files
```python
from pycar.car.compressed_archive import CARv1Writer
from pycar.car.utils import folder_to_dag

with CARv1Writer(file=None, name="example.car") as car_writer:
    cid = folder_to_dag(car_writer, "./path/to/folder", chunk_size=262144)
    print("CARv1 CID:", cid)
```

### Converting Files to CARv1 Files
```python
from pycar.car.compressed_archive import CARv1Writer
from pycar.file_types import BinaryFile

with open("dummy_file_path", "rb") as f:
    with CARv1Writer(
        BinaryFile(bufferedReader=f, chunkSize=1, metadata={"name": "dummyfile"}),
            "dummyfile.car",
            unixfs=True,
            max_children=1024,
        ) as car:
            cid = car.get_car()
    print("CARv1 CID:", cid)
```

### Example Merkle-DAGs generated with this module

#### A pure text file:
[![txt-dag.png](https://i.postimg.cc/fLNFWQD0/txt-dag.png)](https://postimg.cc/PLSKKcLt)

#### A DNA sequence:
[![dna-dag.png](https://i.postimg.cc/t4LR5JNQ/dna-dag.png)](https://postimg.cc/rDNLy8HQ)
