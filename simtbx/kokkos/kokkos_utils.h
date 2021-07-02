#ifndef SIMTBX_KOKKOS_UTILS_H
#define SIMTBX_KOKKOS_UTILS_H

#include "scitbx/array_family/shared.h"
#include "scitbx/array_family/flex_types.h"
#include "simtbx/kokkos/kokkos_types.h"

namespace {
  template <typename T, typename U>
  void
  transfer_X2kokkos(view_1d_t<T> &dst, const U &src) {
    auto host_view = Kokkos::create_mirror_view(dst);
    auto src_ptr = src.begin();
    for (int i=0; i<src.size(); ++i) {
      host_view( i ) = src_ptr[ i ];
    }
    Kokkos::deep_copy(dst, host_view);
  }

  template <typename T, typename U>
  void
  transfer_kokkos2X(T &dst, const view_1d_t<U> &src) {
    auto host_view = Kokkos::create_mirror_view(src);
    Kokkos::deep_copy(host_view, src);
    auto dst_ptr = dst.begin();
    for (int i=0; i<host_view.span(); ++i) {
      dst_ptr[ i ] = host_view( i );
    }
  }
}

namespace simtbx { namespace Kokkos { 

namespace af = scitbx::af;

  template <typename T>
  void
  transfer_shared2kokkos(view_1d_t<T> &dst, const af::shared<T>  &src) {
    if (true) {
      printf("== Transfer %s from %p\n", dst.label().c_str(), (void*) dst.data());
      printf(" - size src|dst: %d|%d\n", src.size(), dst.span() );
    }
    if (dst.span() < src.size()) {
      resize(dst, src.size());
      printf(" - size changed, new size: %d\n", dst.span() );
    }

    transfer_X2kokkos(dst, src);
    //print_view(dst);
  }

  template <typename T>
  void
  transfer_kokkos2shared(af::shared<T> &dst, const view_1d_t<T> &src) {
    if (true) {
      printf("== Transfer %s from %p\n", src.label().c_str(), (void*) src.data());
    }
    transfer_kokkos2X(dst, src);
  }

  template <typename T>
  void
  transfer_kokkos2flex(af::flex_double &dst, const view_1d_t<T> &src) {
    if (true) {
      printf("== Transfer %s from %p\n", src.label().c_str(), (void*) src.data());
    }
    transfer_kokkos2X(dst, src);
  }

  template <typename T>
  void
  transfer_kokkos2flex(af::flex_int &dst, const view_1d_t<T> &src) {
    if (true) {
      printf("== Transfer %s from %p\n", src.label().c_str(), (void*) src.data());
    }
    transfer_kokkos2X(dst, src);
  }

} // Kokkos
} // simtbx

#endif // SIMTBX_KOKKOS_UTILS_H