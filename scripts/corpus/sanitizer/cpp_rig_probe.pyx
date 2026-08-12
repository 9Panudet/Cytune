# distutils: language = c++
# cython: language_level=3
# Mini-I-3 C++ RIG validation (Step 1.1.1 cond 3): NON-VACUOUS — exercises STL behavior
# + UBSan C++ checks (vptr/RTTI) + an STL leak, not just exception unwinding. The rig must
# (a) run clean STL with no false positive, (b) map C++ exceptions to stable Python types,
# (c) CATCH real C++ bugs (heap-OOB, iterator-invalidation UAF, vptr), (d) detect STL leaks.
# Driver: scripts/corpus/sanitizer/rig_audit.sh, in image X' (:phase1).
cdef extern from * nogil:
    """
    #include <vector>
    #include <algorithm>
    #include <stdexcept>
    // (a) clean STL — must NOT trip any sanitizer
    static long _clean_stl() {
        std::vector<int> v; for (int i=0;i<2000;i++) v.push_back(i);
        std::sort(v.begin(), v.end());
        long s=0; for (size_t i=0;i<v.size();++i) s+=v[i]; return s;
    }
    // (b) C++ exception sources (Cython except+ -> Python)
    static void _cpp_oor()   { throw std::out_of_range("oor"); }
    static void _cpp_len()   { throw std::length_error("len"); }
    static void _cpp_inval() { throw std::invalid_argument("inval"); }
    // (c) NON-VACUITY: real C++ bugs the rig MUST catch
    static int _bug_oob() { std::vector<int> v(10,7); volatile int* p=v.data(); return p[64]; }            // ASan heap-buffer-overflow
    static int _bug_uaf() { std::vector<int> v; v.push_back(1); volatile int* p=&v[0];
                            for(int i=0;i<100000;i++) v.push_back(i); return *p; }                          // ASan heap-use-after-free (realloc)
    struct _B { virtual int f(){return 1;} virtual ~_B(){} };
    struct _D : _B { int x; _D():x(42){} int f() override {return x;} };
    static int _bug_vptr() { _B b; _B* pb=&b; _D* pd=reinterpret_cast<_D*>(pb); return pd->f(); }           // UBSan vptr (wrong dynamic type)
    // (d) STL leak — never freed, NOT a CPython allocation
    static long _stl_leak() { std::vector<int>* v=new std::vector<int>(4096,9); return (long)v->size(); }
    """
    long _clean_stl()
    void _cpp_oor()   except +
    void _cpp_len()   except +
    void _cpp_inval() except +
    int _bug_oob()
    int _bug_uaf()
    int _bug_vptr()
    long _stl_leak()

def clean_stl():              return _clean_stl()
def raise_out_of_range():     _cpp_oor()
def raise_length_error():     _cpp_len()
def raise_invalid_argument(): _cpp_inval()
def bug_oob():  return _bug_oob()
def bug_uaf():  return _bug_uaf()
def bug_vptr(): return _bug_vptr()
def stl_leak(): return _stl_leak()
