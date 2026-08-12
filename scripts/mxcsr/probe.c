/* Step 0.1.5 MXCSR probe (grounds roadmap §3.2(2) FTZ/DAZ containment).
 *
 * Prints the SSE MXCSR control word (FTZ = bit 15 / 0x8000, DAZ = bit 6 / 0x0040;
 * power-on default 0x1f80) before dlopen, after dlopen of the .so given as argv[1],
 * and after calling its kernel. Also evaluates a subnormal expression so an active
 * DAZ/FTZ is visible semantically, not just in the control word.
 *
 * Built twice:
 *   probe      : -O2 -ffp-contract=off            (IEEE host process — the rig case)
 *   probe_fast : -O2 -ffast-math -ffp-contract=fast (executable-startup case: shows
 *                what crtfastmath.o does when linked into the *executable*)
 */
#include <dlfcn.h>
#include <stdio.h>
#include <xmmintrin.h>

static void show(const char *when) {
    unsigned csr = _mm_getcsr();
    printf("%-13s MXCSR=0x%04x FTZ=%u DAZ=%u\n", when, csr,
           (csr >> 15) & 1u, (csr >> 6) & 1u);
}

static void subnormal_demo(const char *when) {
    volatile double tiny = 5e-324; /* smallest positive subnormal double */
    volatile double r = tiny * 2.0;
    printf("%-13s subnormal 5e-324*2 = %.17g (%s)\n", when, r,
           r == 0.0 ? "flushed: DAZ/FTZ active" : "preserved: IEEE gradual underflow");
}

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: %s <kernel.so>\n", argv[0]); return 2; }
    show("before-dlopen");
    subnormal_demo("before-dlopen");
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen failed: %s\n", dlerror()); return 2; }
    show("after-dlopen");
    subnormal_demo("after-dlopen");
    double (*f)(double, double, double);
    *(void **)&f = dlsym(h, "kernel");
    if (f) printf("kernel(0.1,0.2,0.3) = %.17g\n", f(0.1, 0.2, 0.3));
    show("after-call");
    return 0;
}
