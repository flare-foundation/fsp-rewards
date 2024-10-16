import json

from web3 import Web3
from web3.middleware import geth_poa_middleware

def wei_to_flr(gwei_amount):
    return gwei_amount / 1e18

if __name__ == '__main__':
    rpc = 'https://flare.aureusox.com/ext/bc/C/rpc'
    web3 = Web3(Web3.HTTPProvider(rpc))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    file_for_key = '../../.keys/ftso_flare_v2_claim_executor'
    password = input('Password for executor:')

    with open(file_for_key) as keyfile:
        encrypted_key = keyfile.read()

        private_key = web3.eth.account.decrypt(encrypted_key, password)
        executor_account = web3.eth.account.from_key(private_key)

    with open('abis/reward_manager_abi.json') as abi_file:
        reward_manager_abi = json.load(abi_file)
    
    print(executor_account.address)

    reward_epochs_to_claim = list(map(int, input('Reward epochs to claim (comma separated): ').replace(" ", "").split(',')))
    recipient = web3.toChecksumAddress(input('Where do you want to send rewards?: '))
    wrap = input('Do you want to wrap rewards? [y/n]: ')
    if wrap == 'y':
        wrap = True
    elif wrap == 'n':
        wrap = False
    else:
        print('Please answer y or n')
        exit()
        

    reward_manager_contract_address = web3.toChecksumAddress('0xC8f55c5aA2C752eE285Bd872855C749f4ee6239B')
    reward_manager_contract = web3.eth.contract(address=reward_manager_contract_address,
                                                        abi=reward_manager_abi)

    entity_address = web3.toChecksumAddress('0xE3b7968c1B706461A8f63540080ECF4Ce70C30c0')

    # Build Proofs from Json's
    tx = {}
    proofs = []
    total_rewards = []  # just for logging purposes
    for reward_epoch in reward_epochs_to_claim:
        file_path = f'../../flare/{reward_epoch}/reward-distribution-data.json'
        
        # Open and load the JSON file
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)

        for reward_claim in data['rewardClaims']:
            if web3.toChecksumAddress(reward_claim['body']['beneficiary'])== entity_address:
                merkle_proof = [web3.toBytes(hexstr=p) for p in reward_claim['merkleProof']]
                reward_epoch_id = reward_claim['body']['rewardEpochId']
                beneficiary = web3.toBytes(hexstr=reward_claim['body']['beneficiary'])[:20]
                claim_type = reward_claim['body']['claimType']
                amount = int(reward_claim['body']['amount'])

                # Build the RewardClaimWithProof tuple
                reward_claim_with_proof = (
                    merkle_proof,
                    (reward_epoch_id, beneficiary, amount, claim_type)
                )
                proofs.append(reward_claim_with_proof)
                total_rewards.append(amount)
                
                break

    reward_epoch = max(reward_epochs_to_claim)

    # Show Details
    total_rewards = round(wei_to_flr(sum(total_rewards)), 4)
    print(f'\n\n ---- TX Details ---- \n reward_owner: {entity_address} \n recipient: {recipient} \n reward_epoch: {reward_epoch} ({reward_epochs_to_claim}) \n wrap: {wrap} \n proofs: {proofs} \n total rewards: {total_rewards}')

    tx = reward_manager_contract.functions.claim(entity_address, recipient, reward_epoch, wrap, proofs).buildTransaction({
        'from': executor_account.address,
        'nonce': web3.eth.get_transaction_count(executor_account.address)
    })

    # confirm before sending
    confirm = str(input(f'\nConfirm\n[y,n]:  '))
    if confirm == 'y':
        signed_tx = executor_account.signTransaction(tx)
        tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)

        print(tx_hash.hex())