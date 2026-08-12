# distutils: language = c++
# cython: language_level=3
# Mini-I-3 C++ extension probe (Step 1.1.1, condition 3): characterize libstdc++ +
# C++-exception behavior under ASan+UBSan, and the Cython C++->Python exception map
# the oracle (§3.1 exception-identity) compares against. Driven by
# scripts/corpus/sanitizer/run_cpp_sanitizer_probe.sh inside image X' (:phase1).
from libcpp.vector cimport vector

cdef extern from * nogil:
    """
    #include <stdexcept>
    static void _cpp_oor()   { throw std::out_of_range("cpp out_of_range"); }
    static void _cpp_len()   { throw std::length_error("cpp length_error"); }
    static void _cpp_inval() { throw std::invalid_argument("cpp invalid_argument"); }
    """
    void _cpp_oor()   except +
    void _cpp_len()   except +
    void _cpp_inval() except +

def use_vector(int n):
    cdef vector[int] v
    cdef int i
    for i in range(n):
        v.push_back(i)
    cdef long s = 0
    for i in range(<int>v.size()):
        s += v[i]
    return s

def raise_out_of_range():     _cpp_oor()
def raise_length_error():     _cpp_len()
def raise_invalid_argument(): _cpp_inval()
