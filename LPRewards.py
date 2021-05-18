from web3 import Web3
from utils import create_contract, fetch_events
import private
import requests
import json
import copy
import time
from etherscan.accounts import Account
from Fuse_Explorer_API.account import Account as AccountFuse

ONLY_CHECK_CURRENT = True
CONTRACTabi = [{"constant":False,"inputs":[],"name":"withdrawInterest","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},{"constant":False,"inputs":[{"name":"_amount","type":"uint256"}],"name":"withdrawStakeAndInterest","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},{"constant":False,"inputs":[],"name":"updateGlobalYield","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},{"constant":True,"inputs":[],"name":"interestData","outputs":[{"name":"globalTotalStaked","type":"uint256"},{"name":"globalYieldPerToken","type":"uint256"},{"name":"lastUpdated","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"vaultAddress","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"getStakeToken","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"getRewardToken","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"stakingStartTime","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"totalReward","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[{"name":"_staker","type":"address"}],"name":"getYieldData","outputs":[{"name":"","type":"uint256"},{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":False,"inputs":[{"name":"_amount","type":"uint256"}],"name":"stake","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"},{"constant":True,"inputs":[],"name":"stakingPeriod","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[{"name":"_staker","type":"address"}],"name":"getStakerData","outputs":[{"name":"","type":"uint256"},{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[{"name":"_staker","type":"address"}],"name":"calculateInterest","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[{"name":"_staker","type":"address"}],"name":"getStatsData","outputs":[{"name":"","type":"uint256"},{"name":"","type":"uint256"},{"name":"","type":"uint256"},{"name":"","type":"uint256"},{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},{"inputs":[{"name":"_stakeToken","type":"address"},{"name":"_rewardToken","type":"address"},{"name":"_stakingPeriod","type":"uint256"},{"name":"_totalRewardToBeDistributed","type":"uint256"},{"name":"_stakingStart","type":"uint256"},{"name":"_vaultAdd","type":"address"}],"payable":False,"stateMutability":"nonpayable","type":"constructor"},{"anonymous":False,"inputs":[{"indexed":True,"name":"staker","type":"address"},{"indexed":False,"name":"value","type":"uint256"},{"indexed":False,"name":"_globalYieldPerToken","type":"uint256"}],"name":"Staked","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"name":"staker","type":"address"},{"indexed":False,"name":"value","type":"uint256"},{"indexed":False,"name":"_globalYieldPerToken","type":"uint256"}],"name":"StakeWithdrawn","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"name":"staker","type":"address"},{"indexed":False,"name":"_value","type":"uint256"},{"indexed":False,"name":"_globalYieldPerToken","type":"uint256"}],"name":"InterestCollected","type":"event"}]

web3Dict = {'main' : Web3(Web3.HTTPProvider((private.RPC_ADDRESS_ETH),request_kwargs={'timeout': 60})),'fuse' : Web3(Web3.HTTPProvider((private.RPC_ADDRESS_FUSE),request_kwargs={'timeout': 60})),'bsc' :  Web3(Web3.HTTPProvider((private.RPC_ADDRESS_BSC),request_kwargs={'timeout': 60}))}
lpRewardsFileURL = 'https://raw.githubusercontent.com/fuseio/fuse-lp-rewards/master/config/default.json'
activePools = {'main' : {},'fuse' : {},'bsc' : {}}

def isActive(endTime):
    return endTime > time.time()

def pullCurrentLPs():
    print("pulling active pools")
    response = requests.get(lpRewardsFileURL)
    with open('rewards.json', mode='wb') as file:
        file.write(response.content)

    with open('rewards.json') as f:
        data = json.load(f)

    for network in data['contracts']:
        for contract in data['contracts'][network]:
            if ONLY_CHECK_CURRENT:
                tempContract = create_contract(web3Dict[network],CONTRACTabi,contract)
                time = tempContract.functions.stakingStartTime().call() + tempContract.functions.stakingPeriod().call()
                if isActive(time):
                    activePools[network][contract] = copy.deepcopy(data['contracts'][network][contract])
            else:
                activePools[network][contract] = copy.deepcopy(data['contracts'][network][contract])

def parseData():
    for network in activePools:
        if network != 'bsc':
            for contract in activePools[network]:
                LPContract = create_contract(web3Dict[network],CONTRACTabi,contract)
                api = Account(address=Web3.toChecksumAddress(contract), api_key=private.API_KEY)
                startBlock = 0
                if network == 'main':
                    transactions = api.get_transaction_page(page=1, offset=10000, sort='des',
                                                            internal=False)
                    startBlock = int(transactions[0]['blockNumber'])
                elif network == 'fuse':
                    apiFuse = AccountFuse(address=contract)
                    transactions = apiFuse.get_tx_list(offset=10000)

                    startBlock = int(transactions[0]['blockNumber'])
                elif network == 'bsc':
                    startBlock = 7276975

                stakingEvents = list(fetch_events(LPContract.events.Staked, from_block=startBlock))
                withdrawEvents = list(fetch_events(LPContract.events.StakeWithdrawn, from_block=startBlock))
                InterestCollected = list(fetch_events(LPContract.events.InterestCollected, from_block=startBlock))
                activePools[network][contract]['stakingEvents'] = {}
                activePools[network][contract]['currentStakers'] = {}
                activePools[network][contract]['withdrawEvents'] = {}
                activePools[network][contract]['claimEvents'] = {}

                counter = 0
                for sEvent in stakingEvents:
                    activePools[network][contract]['stakingEvents'][counter] = {}
                    activePools[network][contract]['stakingEvents'][counter]['staker'] = sEvent['args']['staker']
                    activePools[network][contract]['stakingEvents'][counter]['amount'] = sEvent['args']['value'] / 10**18
                    activePools[network][contract]['stakingEvents'][counter]['block'] = sEvent['blockNumber']
                    activePools[network][contract]['stakingEvents'][counter]['hash'] = Web3.toHex(sEvent['blockHash'])
                    if sEvent['args']['staker'] not in activePools[network][contract]['currentStakers']:
                        activePools[network][contract]['currentStakers'][sEvent['args'].staker] = {}
                        activePools[network][contract]['currentStakers'][sEvent['args']['staker']]['amount'] = sEvent['args']['value'] / 10**18
                        activePools[network][contract]['currentStakers'][sEvent['args']['staker']]['claimed'] = 0
                    else:
                        activePools[network][contract]['currentStakers'][sEvent['args']['staker']]['amount'] += sEvent['args']['value'] / 10 ** 18
                    counter += 1

                counter = 0
                for cEvent in InterestCollected:
                    activePools[network][contract]['claimEvents'][counter] = {}
                    activePools[network][contract]['claimEvents'][counter]['staker'] = cEvent['args']['staker']
                    activePools[network][contract]['claimEvents'][counter]['amount'] = cEvent['args']['_value'] / 10 ** 18
                    activePools[network][contract]['claimEvents'][counter]['block'] = cEvent['blockNumber']
                    activePools[network][contract]['claimEvents'][counter]['hash'] = Web3.toHex(cEvent['blockHash'])
                    activePools[network][contract]['currentStakers'][cEvent['args']['staker']]['claimed'] += cEvent['args']['_value'] / 10 ** 18
                    counter += 1

                counter = 0
                for wEvent in withdrawEvents:
                    activePools[network][contract]['withdrawEvents'][counter] = {}
                    activePools[network][contract]['withdrawEvents'][counter]['staker'] = wEvent['args']['staker']
                    activePools[network][contract]['withdrawEvents'][counter]['amount'] = wEvent['args']['value'] / 10**18
                    activePools[network][contract]['withdrawEvents'][counter]['block'] = wEvent['blockNumber']
                    activePools[network][contract]['withdrawEvents'][counter]['hash'] = Web3.toHex(wEvent['blockHash'])
                    activePools[network][contract]['currentStakers'][wEvent['args']['staker']]['amount'] -= wEvent['args']['value'] / 10**18
                    if activePools[network][contract]['currentStakers'][wEvent['args']['staker']]['amount'] == 0.0:
                        del activePools[network][contract]['currentStakers'][wEvent['args']['staker']]
                    counter += 1



                test = 1

if __name__ == '__main__':
    print("Grabbing LP rewards data")

    pullCurrentLPs()
    parseData()

    outputJSON = {'main' :{}, 'fuse' :{}}

    for network in activePools:
        if network != 'bsc':
            for contract in activePools[network]:
                outputJSON[network][contract] = {}
                outputJSON[network][contract]['currentStakers'] = copy.deepcopy(activePools[network][contract]['currentStakers'])
                outputJSON[network][contract]['stakingEvents'] = copy.deepcopy(activePools[network][contract]['stakingEvents'])
                outputJSON[network][contract]['withdrawEvents'] = copy.deepcopy(activePools[network][contract]['withdrawEvents'])
                outputJSON[network][contract]['claimEvents'] = copy.deepcopy(activePools[network][contract]['claimEvents'])

    with open('results.json', 'w') as fp:
        json.dump(outputJSON, fp)

test = 1
