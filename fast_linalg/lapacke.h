#pragma once

/// Overloads of LAPACKE functions
/**
 *   Some terms used throughout:
 *
 *   - RFP, for Rectangular Full Packed: a format for symmetric and triangular
 *     matrices that takes the same amount of space as the traditional
 *     packed format but allows BLAS level 3 algorithms to be used.
 */
#include <string>
#include <scitbx/error.h>
#ifndef lapack_int
 // note: this can be long
#define lapack_int int
#endif

namespace fast_linalg {
  const int LAPACK_ROW_MAJOR = 101,
    LAPACK_COL_MAJOR = 102;
}

#if defined(USE_FAST_LINALG)
#include <boost/config.hpp>
#ifndef fast_linalg_api
#define fast_linalg_api BOOST_SYMBOL_EXPORT
#endif

extern "C" {
  fast_linalg_api bool is_fast_linalg_initialised();
  // throws exceptions
  fast_linalg_api void initialise_fast_linalg(const std::string &lib_name);

  /// deletes stored wrapper pointer and the shared library handle
  fast_linalg_api void finalise_fast_linalg();

  fast_linalg_api lapack_int lapack_pftrf(int matrix_order, char transr,
    char uplo, lapack_int n, double* a);
  fast_linalg_api lapack_int lapack_spftrf(int matrix_order, char transr,
    char uplo, lapack_int n, float* a);

  fast_linalg_api lapack_int lapack_sfrk(int matrix_order, char transr,
    char uplo, char trans, lapack_int n, lapack_int k, double alpha,
    const double* a, lapack_int lda, double beta,
    double* c);
  fast_linalg_api lapack_int lapack_ssfrk(int matrix_order, char transr,
    char uplo, char trans, lapack_int n, lapack_int k, float alpha,
    const float* a, lapack_int lda, float beta,
    float* c);

  fast_linalg_api lapack_int lapack_tfttp(int matrix_order, char transr,
    char uplo, lapack_int n, const double* arf, double* ap);
  fast_linalg_api lapack_int lapack_stfttp(int matrix_order, char transr,
    char uplo, lapack_int n, const float* arf, float* ap);

  fast_linalg_api lapack_int lapack_tpttf(int matrix_order, char transr,
    char uplo, lapack_int n, const double* ap, double* arf);
  fast_linalg_api lapack_int lapack_stpttf(int matrix_order, char transr,
    char uplo, lapack_int n, const float* ap, float* arf);

  fast_linalg_api lapack_int lapack_pftri(int matrix_order, char transr,
    char uplo, lapack_int n, double* a);
  fast_linalg_api lapack_int lapack_spftri(int matrix_order, char transr,
    char uplo, lapack_int n, float* a);

  fast_linalg_api void cblas_dsyrk(int Order, int Uplo, int Trans, int N, int K,
    double alpha, double *A, int lda, double beta, double *C, int ldc);
};

namespace fast_linalg {
  bool is_initialised() {
    return is_fast_linalg_initialised();
  }

  /// pass lib name like 'openblas.so' or full library path
  void initialise(const std::string &lib_name) {
    initialise_fast_linalg(lib_name);
  }

  /// cleans up the library
  void finalise() {
    finalise_fast_linalg();
  }

  /// @name Cholesky factorisation of A in-place (RFP)
  //@{
  lapack_int pftrf(int matrix_order, char transr, char uplo,
    lapack_int n, double* a)
  {
    return lapack_pftrf(matrix_order, transr, uplo, n, a);
  }

  lapack_int pftrf(int matrix_order, char transr, char uplo,
    lapack_int n, float* a)
  {
    return lapack_spftrf(matrix_order, transr, uplo, n, a);
  }
  //@}

  /// @name Rank-k update (RFP)
  //@{
  lapack_int sfrk(int matrix_order, char transr,
    char uplo, char trans, lapack_int n, lapack_int k, double alpha,
    const double* a, lapack_int lda, double beta,
    double* c)
  {
    return lapack_sfrk(matrix_order, transr,
      uplo, trans, n, k, alpha, a, lda, beta, c);
  }

  lapack_int sfrk(int matrix_order, char transr,
    char uplo, char trans, lapack_int n, lapack_int k, float alpha,
    const float* a, lapack_int lda, float beta,
    float* c)
  {
    return lapack_ssfrk(matrix_order, transr,
      uplo, trans, n, k, alpha, a, lda, beta, c);
  }
  //@}

  /// @name Copies arf in RFP format to ap in standard packed format
  //@{
  lapack_int tfttp(int matrix_order, char transr,
    char uplo, lapack_int n, const double* arf, double* ap)
  {
    return lapack_tfttp(matrix_order, transr, uplo, n, arf, ap);
  }

  lapack_int tfttp(int matrix_order, char transr,
    char uplo, lapack_int n, const float* arf, float* ap)
  {
    return lapack_stfttp(matrix_order, transr, uplo, n, arf, ap);
  }
  //@}

  /// @name Copies ap in standard packed format to arf in RFP format
  //@{
  lapack_int tpttf(int matrix_order, char transr, char uplo,
    lapack_int n, const double* ap, double* arf)
  {
    return lapack_tpttf(matrix_order, transr, uplo, n, ap, arf);
  }

  lapack_int tpttf(int matrix_order, char transr, char uplo,
    lapack_int n, const float* ap, float* arf)
  {
    return lapack_stpttf(matrix_order, transr, uplo, n, ap, arf);
  }
  //@}

  /// @name Inverse of Cholesky decomposed matrix (RFP)
  //@{
  lapack_int pftri(int matrix_order, char transr, char uplo,
    lapack_int n, double* a)
  {
    return lapack_pftri(matrix_order, transr, uplo, n, a);
  }

  lapack_int pftri(int matrix_order, char transr, char uplo,
    lapack_int n, float* a)
  {
    return lapack_spftri(matrix_order, transr, uplo, n, a);
  }
  //@}

  /// @name Performs a symmetric rank-k update
  //@{
  void dsyrk(int Order, int Uplo, int Trans, int N, int K,
    double alpha, double *A, int lda, double beta, double *C, int ldc)
  {
    cblas_dsyrk(Order, Uplo, Trans, N, K, alpha, A, lda, beta, C, ldc);
  }
  //@}
}
#else
namespace fast_linalg {

  bool is_initialised() {
    return false;
  }

  void initialise(const std::string &lib_name) {
    SCITBX_NOT_IMPLEMENTED();
  }

  void finalise() {
    SCITBX_NOT_IMPLEMENTED();
  }

  template <typename FloatType>
  lapack_int pftrf(int matrix_order, char transr, char uplo,
    lapack_int n, FloatType* a)
  {
    SCITBX_NOT_IMPLEMENTED();
    return 0;
  }

  template <typename FloatType>
  lapack_int sfrk(int matrix_order, char transr,
    char uplo, char trans, lapack_int n, lapack_int k, FloatType alpha,
    const FloatType* a, lapack_int lda, FloatType beta,
    FloatType* c)
  {
    SCITBX_NOT_IMPLEMENTED();
    return 0;
  }

  template <typename FloatType>
  lapack_int tfttp(int matrix_order, char transr,
    char uplo, lapack_int n, const FloatType* arf, FloatType* ap)
  {
    SCITBX_NOT_IMPLEMENTED();
    return 0;
  }

  template <typename FloatType>
  lapack_int tpttf(int matrix_order, char transr, char uplo,
    lapack_int n, const FloatType* ap, FloatType* arf)
  {
    SCITBX_NOT_IMPLEMENTED();
    return 0;
  }

  template <typename FloatType>
  lapack_int pftri(int matrix_order, char transr, char uplo,
    lapack_int n, FloatType* a)
  {
    SCITBX_NOT_IMPLEMENTED();
    return 0;
  }

  void dsyrk(int, int, int, int, int, double, double *, int,
    double , double *, int)
  {
    SCITBX_NOT_IMPLEMENTED();
  }
}

#endif // USE_FAST_LINALG
