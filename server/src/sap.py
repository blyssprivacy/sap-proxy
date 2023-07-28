import numpy as np
from numpy.typing import NDArray

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


NONCE_LENGTH = 16


def aes_prng(key: bytes, nonce: bytes, length: int) -> NDArray[np.uint8]:
    """
    Returns a cryptographically secure, deterministically random byte string
    of the requested length, generated using AES-CTR.
    """
    # Set up AES cipher
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes")
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
    # Get the number of bytes we need to generate
    num_bytes = length
    encryptor = cipher.encryptor()

    # Generate random bytes by encrypting a sequence of zeros
    prng_bytes = encryptor.update(b"\x00" * num_bytes)

    return np.frombuffer(prng_bytes, dtype=np.uint8)


def aes_uniform(key: bytes, nonce: bytes, length: int) -> NDArray[np.float32]:
    """
    Return uniformly distributed float32 random numbers in the range [0, 1).
    Does not account for floating point rounding bias.
    """
    random_bytes = aes_prng(key, nonce, length * 4)
    encrypted_numbers = (
        random_bytes.view(np.uint32).astype(np.float64) / (np.iinfo(np.uint32).max)
    ).astype(np.float32)

    return encrypted_numbers


def aes_permutation(key: bytes, length: int) -> NDArray[np.uint64]:
    """
    Returns a deterministically randomized permutation of the integers
    in the range [0, length).
    """
    permutation = np.arange(length, dtype=np.uint64)
    random_bytes = aes_prng(key, b"\x00" * NONCE_LENGTH, length * permutation.itemsize)
    random_integers = random_bytes.view(permutation.dtype)

    for i in range(length - 1):
        encrypted_number = int(random_integers[i])
        j = i + encrypted_number % (length - i)
        permutation[i], permutation[j] = permutation[j], permutation[i]

    return permutation


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

    # deterministic permutation over D, applied to all vectors encrypted with this key
    D = plainvec.shape[-1]
    shuffle_map = aes_permutation(key, D)
    # [D]
    if len(plainvec.shape) == 1:
        shuffled = plainvec[shuffle_map]
    else:
        shuffled = plainvec[..., shuffle_map]

    if beta > 0:
        # generate unique noise for each element, scaled by beta
        noise = (aes_uniform(key, nonce, D) - 0.5) * beta * 2
        # [D,]
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
    D = ciphervec.shape[-1]
    if beta > 0:
        noise = (aes_uniform(key, nonce, D) - 0.5) * beta * 2
        shuffled = ciphervec - noise
    else:
        shuffled = ciphervec

    shuffle_map = aes_permutation(key, D)
    unshuffle_map = np.argsort(shuffle_map)
    plainvec = shuffled[unshuffle_map]

    return plainvec


def test():
    # test permutation
    key = b"\x00" * 32
    length = 10

    s = np.arange(length, dtype=np.uint64)
    p = aes_permutation(key, length)
    s = s[p]
    print(s, p)


if __name__ == "__main__":
    test()
