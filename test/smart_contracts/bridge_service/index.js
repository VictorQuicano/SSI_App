const { Web3 } = require("web3");
const { IndySDK } = require("indy-sdk");
const express = require("express");

class IndyQuorumBridge {
  constructor() {
    this.web3 = new Web3("http://localhost:8545");
    this.app = express();
    this.setupRoutes();
  }

  setupRoutes() {
    this.app.post("/api/verify-and-execute", this.verifyAndExecute.bind(this));
    this.app.get("/api/did/:did", this.getDIDFromQuorum.bind(this));
  }

  async verifyAndExecute(req, res) {
    try {
      const { vcProof, contractAddress, functionCall, parameters } = req.body;

      // 1. Verificar VC con Aries/Indy
      const isVerified = await this.verifyVCWithIndy(vcProof);

      if (!isVerified) {
        return res.status(401).json({ error: "VC verification failed" });
      }

      // 2. Ejecutar en Quorum
      const result = await this.executeOnQuorum(
        contractAddress,
        functionCall,
        parameters
      );

      res.json({
        success: true,
        transactionHash: result.transactionHash,
        blockNumber: result.blockNumber,
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  }

  async verifyVCWithIndy(vcProof) {
    // Integración con Aries para verificar credenciales
    // Esto requiere el agente Aries configurado
    return true; // Placeholder
  }

  async executeOnQuorum(contractAddress, functionCall, parameters) {
    const account = this.web3.eth.accounts.privateKeyToAccount(
      "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
    );

    const contract = new this.web3.eth.Contract(
      JSON.parse(functionCall),
      contractAddress
    );
    const transaction = contract.methods.execute(...parameters);

    const txData = {
      from: account.address,
      to: contractAddress,
      data: transaction.encodeABI(),
      gas: 500000,
    };

    const signedTx = await account.signTransaction(txData);
    return await this.web3.eth.sendSignedTransaction(signedTx.rawTransaction);
  }
}

const bridge = new IndyQuorumBridge();
bridge.app.listen(3002, () => {
  console.log("Bridge service running on port 3002");
});
