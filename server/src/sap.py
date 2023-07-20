from typing import Optional
import numpy as np
import hashlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def gen_nonce() -> bytes:
    return np.random.default_rng().bytes(12)


def np_csprng(key: bytes, nonce: bytes, length: int) -> np.ndarray:
    # Set up AES cipher
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes")
    cipher = Cipher(
        algorithms.AES(key), modes.CTR(nonce), backend=default_backend()
    )

    # Get the number of bytes we need to generate
    num_bytes = length * 4
    encryptor = cipher.encryptor()

    # Encrypt a block of zeros
    encrypted_bytes = encryptor.update(b"\x00" * num_bytes)

    # Convert the encrypted bytes to uint32, then divide by max value to get a float in [0, 1)
    encrypted_numbers = (
        np.frombuffer(encrypted_bytes, dtype=np.uint32).astype(np.float64)
        / np.iinfo(np.uint32).max
    ).astype(np.float32)

    return encrypted_numbers


def get_rng(key: bytes, nonce: Optional[bytes] = None) -> np.random.Generator:
    """
    Returns a numpy random generator, based on a key and optional nonce.
    """
    seed = key
    if nonce is not None:
        seed += nonce
    return np.random.Generator(
        np.random.PCG64(seed=np.frombuffer(seed, dtype=np.uint8))
    )


def sap(key: bytes, plainvec: np.ndarray, beta: float, nonce: bytes):
    """
    SAP: Shuffle-and-Perturb

    plainvec: a 1D numpy array, representing a single vector
    beta: scalar factor >= 0.
          Larger beta increases security (i.e. harder to recover plainvec from ciphervec)
          at the cost of less-accurate distance comparisons in the encrypted space.
          When beta=0, no perturbation is applied, and the ciphervec is just a shuffled version of plainvec.
    nonce: a unique integer, used to generate pseudorandom noise for perturbation.
    """
    key_rng = get_rng(key)

    # deterministic permutation over D, applied to all vectors encrypted with this key
    D = plainvec.shape[-1]
    shuffle_map = key_rng.permutation(D)
    # [D]
    if len(plainvec.shape) == 1:
        shuffled = plainvec[shuffle_map]
    else:
        shuffled = plainvec[..., shuffle_map]

    if beta > 0:
        # generate unique noise for each element, scaled by beta
        noise_rng = get_rng(key, nonce)
        noise = noise_rng.uniform(low=-beta, high=beta, size=plainvec.shape)
        # [n, D]
        ciphervec = shuffled + noise
    else:
        ciphervec = shuffled

    return ciphervec


def unsap(key: bytes, ciphervec: np.ndarray, beta: float, nonce: bytes):
    """
    Inverse of SAP

    ciphervec: a 1D numpy array, representing a single vector
    beta: the same beta used in SAP
    nonce: the same nonce used in SAP

    """
    if beta > 0:
        noise_rng = key_rng = get_rng(key, nonce)
        noise = noise_rng.uniform(low=-beta, high=beta, size=ciphervec.shape)
        shuffled = ciphervec - noise
    else:
        shuffled = ciphervec

    key_rng = get_rng(key)
    D = ciphervec.shape[-1]
    shuffle_map = key_rng.permutation(D)
    unshuffle_map = np.argsort(shuffle_map)
    plainvec = shuffled[unshuffle_map]

    return plainvec
