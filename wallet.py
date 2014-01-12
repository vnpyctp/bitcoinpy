#!/usr/bin/env python

import os
from bsddb.db import *
from pickle import dumps, loads

import binascii
from bitcoin.core import COutPoint, CTxIn, CTxOut, CTransaction


# Joric/bitcoin-dev, june 2012, public domain
import hashlib
import ctypes
import ctypes.util
import sys

ssl = ctypes.cdll.LoadLibrary (ctypes.util.find_library ('ssl') or 'libeay32')

def check_result (val, func, args):
    if val == 0: raise ValueError 
    else: return ctypes.c_void_p (val)

ssl.EC_KEY_new_by_curve_name.restype = ctypes.c_void_p
ssl.EC_KEY_new_by_curve_name.errcheck = check_result

class KEY:
    def __init__(self):
        NID_secp256k1 = 714
        self.k = ssl.EC_KEY_new_by_curve_name(NID_secp256k1)
        self.compressed = False
        self.POINT_CONVERSION_COMPRESSED = 2
        self.POINT_CONVERSION_UNCOMPRESSED = 4

    def __del__(self):
        if ssl:
            ssl.EC_KEY_free(self.k)
        self.k = None

    def generate(self, secret=None):
        if secret:
            self.prikey = secret
            priv_key = ssl.BN_bin2bn(secret, 32, ssl.BN_new())
            group = ssl.EC_KEY_get0_group(self.k)
            pub_key = ssl.EC_POINT_new(group)
            ctx = ssl.BN_CTX_new()
            ssl.EC_POINT_mul(group, pub_key, priv_key, None, None, ctx)
            ssl.EC_KEY_set_private_key(self.k, priv_key)
            ssl.EC_KEY_set_public_key(self.k, pub_key)
            ssl.EC_POINT_free(pub_key)
            ssl.BN_CTX_free(ctx)
            return self.k
        else:
            return ssl.EC_KEY_generate_key(self.k)

    def get_pubkey(self):
        size = ssl.i2o_ECPublicKey(self.k, 0)
        mb = ctypes.create_string_buffer(size)
        ssl.i2o_ECPublicKey(self.k, ctypes.byref(ctypes.pointer(mb)))
        return mb.raw

    def get_secret(self):
        bn = ssl.EC_KEY_get0_private_key(self.k);
        bytes = (ssl.BN_num_bits(bn) + 7) / 8
        mb = ctypes.create_string_buffer(bytes)
        n = ssl.BN_bn2bin(bn, mb);
        return mb.raw.rjust(32, chr(0))

    def set_compressed(self, compressed):
        self.compressed = compressed
        if compressed:
            form = self.POINT_CONVERSION_COMPRESSED
        else:
            form = self.POINT_CONVERSION_UNCOMPRESSED
        ssl.EC_KEY_set_conv_form(self.k, form)

def dhash(s):
    return hashlib.sha256(hashlib.sha256(s).digest()).digest()

def rhash(s):
    h1 = hashlib.new('ripemd160')
    h1.update(hashlib.sha256(s).digest())
    return h1.digest()

b58_digits = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def base58_encode(n):
    l = []
    while n > 0:
        n, r = divmod(n, 58)
        l.insert(0,(b58_digits[r]))
    return ''.join(l)

def base58_decode(s):
    n = 0
    for ch in s:
        n *= 58
        digit = b58_digits.index(ch)
        n += digit
    return n

def base58_encode_padded(s):
    res = base58_encode(int('0x' + s.encode('hex'), 16))
    pad = 0
    for c in s:
        if c == chr(0):
            pad += 1
        else:
            break
    return b58_digits[0] * pad + res

def base58_decode_padded(s):
    pad = 0
    for c in s:
        if c == b58_digits[0]:
            pad += 1
        else:
            break
    h = '%x' % base58_decode(s)
    if len(h) % 2:
        h = '0' + h
    res = h.decode('hex')
    return chr(0) * pad + res

def base58_check_encode(s, version=0):
    vs = chr(version) + s
    check = dhash(vs)[:4]
    return base58_encode_padded(vs + check)

def base58_check_decode(s, version=0):
    k = base58_decode_padded(s)
    v0, data, check0 = k[0], k[1:-4], k[-4:]
    check1 = dhash(v0 + data)[:4]
    if check0 != check1:
        raise BaseException('checksum error')
    if version != ord(v0):
        raise BaseException('version mismatch')
    return data

def gen_eckey(passphrase=None, secret=None, pkey=None, compressed=False, rounds=1, version=0):
    k = KEY()
    if passphrase:
        secret = passphrase.encode('utf8')
        for i in xrange(rounds):
            secret = hashlib.sha256(secret).digest()
    if pkey:
        secret = base58_check_decode(pkey, 128+version)
        compressed = len(secret) == 33
        secret = secret[0:32]
    k.generate(secret)
    k.set_compressed(compressed)
    return k

def get_addr(k,version=0):
    pubkey = k.get_pubkey()
    secret = k.get_secret()
    hash160 = rhash(pubkey)
    addr = base58_check_encode(hash160,version)
    payload = secret
    if k.compressed:
        payload = secret + chr(1)
    pkey = base58_check_encode(payload, 128+version)
    print pubkey
    return addr, pkey, binascii.hexlify(pubkey)

def reencode(pkey,version=0):
    payload = base58_check_decode(pkey,128+version)
    secret = payload[:-1]
    payload = secret + chr(1)
    pkey = base58_check_encode(payload, 128+version)
    print get_addr(gen_eckey(pkey))

def scan_block(index, address):
    return 1.0



# Wallet class
class Wallet(object):
    def __init__(self, walletfile = "~/.bitcoinpy/wallet.dat"):
        self.walletfile = os.path.expanduser(walletfile)
        self.walletdir = os.path.split(self.walletfile)[0]
        self.db_env = DBEnv(0)
        self.db_env.open(self.walletdir, (DB_CREATE|DB_INIT_LOCK|DB_INIT_LOG|DB_INIT_MPOOL|DB_INIT_TXN|DB_THREAD|DB_RECOVER))
    
    
    # open wallet database
    def open(self, writable=False):
	    db = DB(self.db_env)
	    if writable:
		    DB_TYPEOPEN = DB_CREATE
	    else:
		    DB_TYPEOPEN = DB_RDONLY
	    flags = DB_THREAD | DB_TYPEOPEN
	    try:
		    r = db.open(self.walletfile, "main", DB_BTREE, flags)
	    except DBError:
		    r = True
	    if r is not None:
		    logging.error("Couldn't open wallet.dat/main. Try quitting Bitcoin and running this again.")
		    sys.exit(1)
	    return db
	
	    	
    # if wallet does not exist, create it
    def initialize(self):
        if not os.path.isfile(self.walletfile):
            walletdb = open_wallet(writable = True)
            print "Initilizing wallet"
            key = gen_eckey()
            address, private_key, public_key = get_addr(key)
            walletdb['account'] = dumps([{"public_key": public_key, "private_key": private_key, "address": address, "balance": 0.0, "height" : 0}])
            walletdb['accounts'] = dumps(['account'])
            walletdb.sync()
            walletdb.close()
    
    
    # create and return a new address
    def getnewaddress(self, account = None):
        if not account:
            account = "account"
        key = gen_eckey()
        address, private_key, public_key = get_addr(key)
        addressmap = {"public_key": public_key, "private_key": private_key, "address": address, "balance": 0.0, "height" : 0}
        walletdb = self.open(writable = True)
        # if wallet is not initialized
        if 'accounts' not in walletdb:
            print "Wallet not initialized ... quitting!"
            return None
        # wallet is initialized
        accounts = loads(walletdb['accounts'])
        if account in accounts:
            addressmaplist = loads(walletdb[account])
            addressmaplist.append(addressmap)
        else:
            print "account: ", account, " not in accounts"
            print "creating new account" 
            addressmaplist = [addressmap]
        walletdb[account] = dumps(addressmaplist)
        walletdb.sync()
        walletdb.close()
        return address

    # return an account
    def getaccount(self, account = None):
        if not account:
            account = "account"
        account = "account" # FIXME 
        walletdb = self.open()
        # if wallet is not initialized, return
        if 'accounts' not in walletdb:
            print "Wallet not initialized ... quitting!"
            return None
        # wallet is initialized
        accounts = loads(walletdb['accounts'])
        if account not in accounts:
            print "Error: Account nto found"
            return
        # if account is wallet 
        addressmaplist = loads(walletdb[account])
        walletdb.close()
        print addressmaplist
        return addressmaplist

    # getaccounts  
    def getaccounts(self):
        walletdb = self.open()
        # if wallet is not initialized, return
        if 'accounts' not in walletdb:
            print "Wallet not initialized ... quitting!"
            return None
        # wallet is initialized
        accounts = loads(walletdb['accounts'])
        walletdb.close()
        for account in accounts:
            addressmaplist = loads(walletdb[account])
            print addressmaplist
        return
    
    # retrn balance of an account
    def getbalance(account):
        """
        walletdb = open_wallet(db_env, walletfile, writable = True)
        # get account
        accountinfo = loads(walletdb[account])
        public_key = accountinfo['public_key']
        private_key = accountinfo['private_key']
        address = accountinfo['address']
        balance = accountinfo['balance']
        height = accountinfo['height']
        
        print "\t Public key: ", public_key
        print "\tPrivate key: ", private_key
        print "\tAddress: ", address
        print "\tBalance: ", balance
        walletdb[account] = dumps({"public_key": "Public key", "private_key": private_key, "address": address, "balance": balance, "height" : height})
        walletdb.close()
        """
        # get chaindb from bitcoinpy
        balance = self.chaindb.getbalance(address)
        return balance

    # send to an address
    def sendtoaddress(self, fromaddress, toaddress, amount):
        print "sending: ", amount, "from address: ", fromaddress, " to address: ", toaddress
        txin = CTxIn()
        txin.prevout = COutPoint()
        # fix the address hardcoding
        txin.prevout.hash = 102036534123695066960262520358268546962206412441328032747133253249363145533949
        txin.prevout.n = 0
        txin.scriptSig = binascii.unhexlify("41046f5ec7490d5eae8e9fda546f6f6ebd1e975d7819de26ab6e581709609d7830662633d155c70c0430b09bb86421467958fb8648ec5ab3b37e3e5d6bc1bbba5368ac")
        # FIXME: FIX the adderss hardcoding stuff ... and also a block needs to be mined too ... for balance check
        txout = CTxOut()
        txout.nValue = 2
        print "TXOUT: ", txout.nValue, type(txout.nValue)
        txout.scriptPubKey = binascii.unhexlify("410450863AD64A87AE8A2FE83C1AF1A8403CB53F53E486D8511DAD8A04887E5B23522CD470243453A299FA9E77237716103ABC11A1DF38855ED6F2EE187E9C582BA6AC")
        tx = CTransaction()
        tx.vin.append(txin)
        tx.vout.append(txout)
        return tx
