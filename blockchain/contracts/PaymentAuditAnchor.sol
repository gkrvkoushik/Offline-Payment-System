// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PaymentAuditAnchor
 * @notice Immutable blockchain anchoring contract for offline payment settlement audit roots.
 * @dev Anchors domain-separated Merkle roots of settlement batches to provide non-repudiation
 *      and independent verifiability without storing raw payment or personal data on-chain.
 *      Includes administrative access control, submitter authorization, duplicate batch protection,
 *      and schema versioning.
 */
contract PaymentAuditAnchor {

    // Current metadata and event schema version
    uint32 public constant SCHEMA_VERSION = 1;

    // Contract administrator / owner
    address public owner;

    // Mapping of authorized settlement submitters
    mapping(address => bool) public isAuthorizedSubmitter;

    struct AnchorRecord {
        bytes32 merkleRoot;
        address submitter;
        uint64 blockTimestamp;
        uint32 schemaVersion;
        bytes32 metadataHash;
    }

    // Mapping from unique batchId to its immutable anchor record
    mapping(bytes32 => AnchorRecord) private _anchors;

    // Events
    event SubmitterAuthorized(address indexed submitter, address indexed authorizedBy);
    event SubmitterRevoked(address indexed submitter, address indexed revokedBy);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    event AuditBatchAnchored(
        bytes32 indexed batchId,
        bytes32 indexed merkleRoot,
        address indexed submitter,
        uint64 blockTimestamp,
        uint32 schemaVersion,
        bytes32 metadataHash
    );

    // Custom errors
    error UnauthorizedCaller(address caller);
    error SubmitterAlreadyAuthorized(address submitter);
    error SubmitterNotAuthorized(address submitter);
    error InvalidZeroAddress();
    error InvalidBatchId();
    error InvalidMerkleRoot();
    error BatchAlreadyExists(bytes32 batchId);
    error AnchorNotFound(bytes32 batchId);

    modifier onlyOwner() {
        if (msg.sender != owner) {
            revert UnauthorizedCaller(msg.sender);
        }
        _;
    }

    modifier onlyAuthorizedSubmitter() {
        if (!isAuthorizedSubmitter[msg.sender] && msg.sender != owner) {
            revert UnauthorizedCaller(msg.sender);
        }
        _;
    }

    constructor() {
        owner = msg.sender;
        isAuthorizedSubmitter[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit SubmitterAuthorized(msg.sender, msg.sender);
    }

    /**
     * @notice Authorize an address to submit settlement audit anchors.
     * @param submitter Address to authorize.
     */
    function addAuthorizedSubmitter(address submitter) external onlyOwner {
        if (submitter == address(0)) {
            revert InvalidZeroAddress();
        }
        if (isAuthorizedSubmitter[submitter]) {
            revert SubmitterAlreadyAuthorized(submitter);
        }
        isAuthorizedSubmitter[submitter] = true;
        emit SubmitterAuthorized(submitter, msg.sender);
    }

    /**
     * @notice Revoke authorization from a settlement submitter.
     * @param submitter Address to revoke.
     */
    function removeAuthorizedSubmitter(address submitter) external onlyOwner {
        if (!isAuthorizedSubmitter[submitter]) {
            revert SubmitterNotAuthorized(submitter);
        }
        isAuthorizedSubmitter[submitter] = false;
        emit SubmitterRevoked(submitter, msg.sender);
    }

    /**
     * @notice Transfer ownership of the contract.
     * @param newOwner Address of the new owner.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) {
            revert InvalidZeroAddress();
        }
        address previousOwner = owner;
        owner = newOwner;
        emit OwnershipTransferred(previousOwner, newOwner);
    }

    /**
     * @notice Anchor a settlement batch Merkle root to the blockchain.
     * @param batchId Unique identifier for the settlement batch.
     * @param merkleRoot The 32-byte domain-separated Merkle root of all batch audit events.
     * @param metadataHash Optional SHA-256 hash of batch metadata (e.g. policy, allowance ID).
     */
    function anchorBatch(
        bytes32 batchId,
        bytes32 merkleRoot,
        bytes32 metadataHash
    ) external onlyAuthorizedSubmitter {
        if (batchId == bytes32(0)) {
            revert InvalidBatchId();
        }
        if (merkleRoot == bytes32(0)) {
            revert InvalidMerkleRoot();
        }
        if (_anchors[batchId].merkleRoot != bytes32(0)) {
            revert BatchAlreadyExists(batchId);
        }

        uint64 currentTimestamp = uint64(block.timestamp);

        _anchors[batchId] = AnchorRecord({
            merkleRoot: merkleRoot,
            submitter: msg.sender,
            blockTimestamp: currentTimestamp,
            schemaVersion: SCHEMA_VERSION,
            metadataHash: metadataHash
        });

        emit AuditBatchAnchored(
            batchId,
            merkleRoot,
            msg.sender,
            currentTimestamp,
            SCHEMA_VERSION,
            metadataHash
        );
    }

    /**
     * @notice Retrieve an anchored record by its batch ID.
     */
    function getAnchor(bytes32 batchId)
        external
        view
        returns (
            bytes32 merkleRoot,
            address submitter,
            uint64 blockTimestamp,
            uint32 schemaVersion,
            bytes32 metadataHash
        )
    {
        AnchorRecord memory record = _anchors[batchId];
        if (record.merkleRoot == bytes32(0)) {
            revert AnchorNotFound(batchId);
        }
        return (
            record.merkleRoot,
            record.submitter,
            record.blockTimestamp,
            record.schemaVersion,
            record.metadataHash
        );
    }

    /**
     * @notice Check whether a batch has been anchored.
     */
    function isBatchAnchored(bytes32 batchId) external view returns (bool) {
        return _anchors[batchId].merkleRoot != bytes32(0);
    }

    /**
     * @notice Verify a Merkle inclusion proof against an anchored root using SHA-256 precompile (0x02).
     * @param batchId The anchored settlement batch ID.
     * @param leafHash Domain-separated leaf hash SHA-256(0x00 || event_data).
     * @param proof Sibling hashes along the audit path.
     * @param isLeft Boolean flag for each sibling (true if sibling is left, false if right).
     */
    function verifyInclusion(
        bytes32 batchId,
        bytes32 leafHash,
        bytes32[] calldata proof,
        bool[] calldata isLeft
    ) external view returns (bool) {
        bytes32 root = _anchors[batchId].merkleRoot;
        if (root == bytes32(0)) {
            return false;
        }
        if (proof.length != isLeft.length) {
            return false;
        }

        bytes32 current = leafHash;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 sibling = proof[i];
            if (isLeft[i]) {
                current = sha256(abi.encodePacked(uint8(1), sibling, current));
            } else {
                current = sha256(abi.encodePacked(uint8(1), current, sibling));
            }
        }

        return current == root;
    }
}
