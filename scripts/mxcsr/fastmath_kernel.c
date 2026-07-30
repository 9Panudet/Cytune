/* Step 0.1.5 MXCSR probe payload. Compiled twice:
 *   fastmath_kernel.so : -O2 -ffast-math -ffp-contract=fast -shared -fPIC
 *   plain_kernel.so    : -O2 -ffp-contract=off -shared -fPIC   (control)
 * The function body is irrelevant to the probe; what matters is whether loading
 * the .so mutates the process MXCSR (crtfastmath.o constructor). */
double kernel(double a, double b, double c) { return a * b + c; }
