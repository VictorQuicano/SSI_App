pragma solidity ^0.8.0;

contract DIDRegistry {
    struct DIDDocument {
        string did;
        string document;
        address owner;
        uint256 created;
        uint256 updated;
    }
    
    mapping(string => DIDDocument) public didDocuments;
    mapping(address => string[]) public ownerDIDs;
    
    event DIDCreated(string indexed did, address owner);
    event DIDUpdated(string indexed did, address owner);
    
    function createDID(
        string memory _did, 
        string memory _document
    ) public {
        require(bytes(didDocuments[_did].did).length == 0, "DID already exists");
        
        didDocuments[_did] = DIDDocument({
            did: _did,
            document: _document,
            owner: msg.sender,
            created: block.timestamp,
            updated: block.timestamp
        });
        
        ownerDIDs[msg.sender].push(_did);
        emit DIDCreated(_did, msg.sender);
    }
    
    function getDID(string memory _did) public view returns (string memory, address, uint256) {
        DIDDocument memory doc = didDocuments[_did];
        return (doc.document, doc.owner, doc.updated);
    }
}