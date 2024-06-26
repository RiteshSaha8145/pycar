from pycar.abstract import File
from pycar.protobufs import PBNode, PBLink, Data  # type: ignore
from contextlib import AbstractContextManager
from multiformats import CID, multihash, varint  # type: ignore
from typing import BinaryIO, Optional, Type, Tuple, Generator
from types import TracebackType
import dag_cbor  # type: ignore
from pycar.utils import prepend_data_to_file
from itertools import islice
from math import log, ceil


class CARv1Writer(AbstractContextManager):
    """
    Context manager for writing data to a CARv1 file.

    Args:
        file (BinaryFile): The binary file object to write to.
        name (str): The name of the CARv1 file to create.
        unixfs (bool): Flag indicating whether to use UnixFS format.

    Attributes:
        file (BinaryFile): The binary file object being written to.
        name (str): The name of the CARv1 file being created.
        bufferedWriter (BinaryIO): The buffered writer for the CARv1 file.
        unixfs (bool): Flag indicating whether to use UnixFS format.
    """

    def __init__(
        self,
        file: Optional[File],
        name: str,
        unixfs: bool = False,
        max_children: int = 1024,
    ):
        """
        Initializes a CARv1Writer object.

        Args:
            file (BinaryFile): The binary file object to write to.
            name (str): The name of the CARv1 file to create.
            unixfs (bool, optional): Flag indicating whether to use UnixFS format. Defaults to False.
            max_children (int, optional): Maximum number of children per node. Defaults to 1024.
        """
        self.file = file
        self.name = name
        self.bufferedWriter: BinaryIO = open(name, "wb")
        self.unixfs = unixfs
        self.max_children = max_children

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
        /,
    ) -> Optional[bool]:
        """
        Exit the context manager and close the buffered writer.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of the exception, if any.
            exc_value (Optional[BaseException]): The exception value, if any.
            traceback (Optional[TracebackType]): The traceback, if any.

        Returns:
                Optional[bool]: True if the buffered writer was closed successfully, False otherwise.
        """
        self.bufferedWriter.close()
        return True

    def _gen_cid(self, data: bytes, codec: str) -> CID:
        """
        Generate a CID for the given data.

        Args:
            data (bytes): The data to calculate the CID for.
            codec (str): The codec to use for the CID.

        Returns:
            CID: The generated CID.
        """
        hash_value: bytes = multihash.digest(data, "sha2-256")
        return CID("base32", version=1, codec=codec, digest=hash_value)

    def _get_block(self, cid: CID, data: bytes) -> bytes:
        """
        Get a block with the given CID and data.

        Args:
            cid (CID): The CID for the block.
            data (bytes): The data for the block.

        Returns:
            bytes: The block data.
        """
        cid = bytes(cid)
        return varint.encode(len(cid) + len(data)) + cid + data

    def _get_pbnode(self, dtype: Data.DataType) -> Tuple[PBNode, Data]:
        """
        Create a PBNode and corresponding UnixFS Data object.

        Args:
            dtype (Data.DataType): The data type for the PBNode.

        Returns:
            Tuple[PBNode, Data]: A tuple containing the PBNode and UnixFS Data objects.
        """
        pbnode: PBNode = PBNode()
        unixfs: Data = Data()
        unixfs.Type = dtype
        return (pbnode, unixfs)

    def _get_pblink(self, cid: CID, name: str, size: int) -> PBLink:
        """
        Create a PBLink object.

        Args:
            cid (CID): The CID for the link.
            name (str): The name of the link.
            size (int): The size of the linked data.

        Returns:
            PBLink: The PBLink object.
        """
        pblink = PBLink()
        pblink.Hash = bytes(cid)
        pblink.Name = name
        pblink.Tsize = size
        return pblink

    def _serialize_and_write_pbnode(
        self, pbnode: PBNode, unixfs: Data, codec: str = "dag-pb"
    ) -> Tuple[bytes, CID]:
        """
        Serialize a PBNode and UnixFS Data object, then write to the CARv1 file.

        Args:
            pbnode (PBNode): The PBNode object to serialize.
            unixfs (Data): The UnixFS Data object to serialize.
            codec (str, optional): The codec to use for serialization. Defaults to "dag-pb".

        Returns:
            Tuple[bytes, CID]: The block data and CID of the serialized node.
        """
        pbnode.Data = unixfs.SerializeToString()
        pbnode_bytes = pbnode.SerializeToString()

        cid = self._gen_cid(data=pbnode_bytes, codec=codec)
        pbnode_block = self._get_block(cid=cid, data=pbnode_bytes)
        self.bufferedWriter.write(pbnode_block)
        return (pbnode_block, cid)

    def _get_raw_node(self) -> Generator[Tuple[bytes, CID], None, None]:
        """
        Generate raw node blocks from the input file.

        Yields:
            Generator[Tuple[bytes, CID], None, None]: Generator of block data and CIDs.
        """
        if not self.file:
            return None
        for raw_data in self.file:

            codec, block = "raw", raw_data
            if self.unixfs:
                pbnode, unixfs = self._get_pbnode(dtype=Data.DataType.Raw)
                unixfs.Data = raw_data
                unixfs.blocksizes.extend([len(raw_data)])
                pbnode.Data = unixfs.SerializeToString()
                codec, block = "dag-pb", pbnode.SerializeToString()

            cid: CID = self._gen_cid(data=block, codec=codec)
            block = self._get_block(cid=cid, data=block)

            self.bufferedWriter.write(block)

            yield (block, cid)

    def _get_intermediate_node(self) -> Generator[Tuple[bytes, CID], None, None]:
        """
        Generate intermediate file node blocks from raw node blocks.

        Yields:
            Generator[Tuple[bytes, CID], None, None]: Generator of block data and CIDs.
        """

        pbnode, unixfs = self._get_pbnode(dtype=Data.DataType.File)
        for i, (data, cid) in enumerate(self._get_raw_node()):
            link = self._get_pblink(cid=cid, name=f"Chunks{i}", size=len(data))
            pbnode.Links.extend([link])
            unixfs.blocksizes.extend([len(data)])

            if (i + 1) % self.max_children == 0:
                pbnode_block, cid = self._serialize_and_write_pbnode(
                    pbnode=pbnode, unixfs=unixfs
                )
                yield (pbnode_block, cid)
                pbnode, unixfs = self._get_pbnode(dtype=Data.DataType.File)

        if len(pbnode.Links) > 0:
            pbnode_block, cid = self._serialize_and_write_pbnode(
                pbnode=pbnode, unixfs=unixfs
            )
            yield (pbnode_block, cid)

    def _build_dag(self) -> Tuple[CID, int]:
        """
        Generate the root node by building layers of file nodes.

        Returns:
            Tuple[CID, int]: The CID of the root node and the number of layers.
        """
        parents = [(len(block), cid) for block, cid in self._get_intermediate_node()]
        layers = int(ceil(log(len(parents), self.max_children)))

        for layer in range(layers):
            new_parents = []
            for starting_index in range(0, len(parents), self.max_children):
                pbnode, unixfs = self._get_pbnode(dtype=Data.DataType.File)
                for i, (size, cid) in enumerate(
                    islice(parents, starting_index, self.max_children + starting_index)
                ):
                    link = self._get_pblink(
                        cid=cid, name=f"File_Layer:{layer}:Chunk{i}", size=size
                    )

                    pbnode.Links.extend([link])
                    unixfs.blocksizes.extend([size])

                pbnode_block, new_cid = self._serialize_and_write_pbnode(
                    pbnode=pbnode, unixfs=unixfs
                )
                new_parents.append((len(pbnode_block), new_cid))

            parents = new_parents

        return parents[0][1]

    def _get_file_node(self, with_name_node=False) -> Optional[Tuple[int, CID]]:
        """
        Get the root node for the CARv1 file.

        Returns:
            CID: The CID of the root node.
        """
        if not self.file:
            return None
        file_cid = self._build_dag()
        size = self.file.bufferedReader.tell()
        if with_name_node:
            pbnode, unixfs = self._get_pbnode(dtype=Data.DataType.File)
            link = self._get_pblink(
                cid=file_cid, name=self.file.metadata["name"], size=size
            )
            pbnode.Links.extend([link])
            unixfs.blocksizes.extend([size])
            _, file_cid = self._serialize_and_write_pbnode(pbnode=pbnode, unixfs=unixfs)
        return (size, file_cid)

    def _write_header(self, cid: CID) -> None:
        encoded_root_node = dag_cbor.encode({"roots": [cid], "version": 1})
        header = varint.encode(len(encoded_root_node)) + encoded_root_node
        self.bufferedWriter.flush()
        prepend_data_to_file(file_name=self.name, data=header)

    def get_car(self) -> Optional[CID]:
        """
        Generate the CARv1 file with the given maximum number of children per node.

        Returns:
            CID: The CID of the root node.
        """
        node = self._get_file_node()
        if not node:
            return None
        _, cid = node
        self._write_header(cid=cid)
        return cid
