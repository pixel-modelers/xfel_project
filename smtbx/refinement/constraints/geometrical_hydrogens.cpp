#include <smtbx/refinement/constraints/geometrical_hydrogens.h>
#include <scitbx/sparse/io.h>

namespace smtbx { namespace refinement { namespace constraints {

  //*** CH3, NH2, OH ***

  std::size_t terminal_tetrahedral_xhn_sites::size() const {
    return 3*x_h.size();
  }

  void
  terminal_tetrahedral_xhn_sites
  ::linearise(uctbx::unit_cell const &unit_cell,
              sparse_matrix_type *jacobian_transpose)
  {
    using namespace constants;
    site_parameter *pivot = (site_parameter *)argument(0),
                   *pivot_neighbour = (site_parameter *)argument(1);
    independent_scalar_parameter
      *azimuth = (independent_scalar_parameter *)argument(2),
      *length  = (independent_scalar_parameter *)argument(3);

    // Local frame
    cart_t x_p = unit_cell.orthogonalize(pivot->value),
           x_pn = unit_cell.orthogonalize(pivot_neighbour->value);
    af::tiny<cart_t, 3>
    e = scitbx::math::orthonormal_basis(x_p - x_pn, e_zero_azimuth);

    double phi = azimuth->value;
    double l = length->value;
    double cos_phi = std::cos(phi), sin_phi = std::sin(phi);

    // Loop over the Hydrogen atoms
    for (int k=0; k < x_h.size(); ++k) {

      // Cosine and Sine of the azimutal angle of the k-th Hydrogen
      /* Mathematica:
       Table[TrigExpand[Cos[\[Phi] + n Pi/3]], {n, {2, 4}}]
       Table[TrigExpand[Sin[\[Phi] + n Pi/3]], {n, {2, 4}}]
       */
      double c, s;
      switch (k) {
        case 0:
          // 1st Hydrogen: azimuthal angle = phi
          c = cos_phi;
          s = sin_phi;
          break;
        case 1:
          // 2nd Hydrogen: azimuthal angle = phi + 2pi/3
          c = -0.5        *cos_phi - half_sqrt_3*sin_phi;
          s =  half_sqrt_3*cos_phi -         0.5*sin_phi;
          break;
        case 2:
          // 3rd Hydrogen: azimuthal angle = phi + 4pi/3
          c = -0.5        *cos_phi + half_sqrt_3*sin_phi;
          s = -half_sqrt_3*cos_phi -         0.5*sin_phi;
        default:
          break;
      }

      // Site of k-th Hydrogen
      cart_t u = sin_tetrahedral_angle*(c*e[1] + s*e[2]) + e[0]/3.;
      x_h[k] = x_p + l*u;

      // Derivatives
      if (!jacobian_transpose) continue;
      sparse_matrix_type &jt = *jacobian_transpose;
      std::size_t const j_h = index() + 3*k;

      // Riding
      for (int i=0; i<3; ++i) {
        jt.col(j_h + i) = jt.col(pivot->index() + i);
      }

      /** We take advantage of the fact that azimuth and length are
          independent variables. So jt.col(azimuth->index()) is either
          zero or is a column of the identity matrix.
       */

      // Rotation
      if (azimuth->is_variable()) {
        cart_t grad_c = l*sin_tetrahedral_angle*(-s*e[1] + c*e[2]);
        frac_t grad_f = unit_cell.fractionalize(grad_c);
        for (int i=0; i<3; ++i) jt(azimuth->index(), j_h + i) = grad_f[i];
      }

      // Bond stretching
      if (length->is_variable()) {
        frac_t grad_f = unit_cell.fractionalize(u);
        for (int i=0; i<3; ++i) jt(length->index(), j_h + i) = grad_f[i];
      }
    }
  }

  void
  terminal_tetrahedral_xhn_sites::store(uctbx::unit_cell const &unit_cell) const
  {
    for (int i=0; i<hydrogen.size(); ++i) {
      hydrogen[i]->site = unit_cell.fractionalize(x_h[i]);
    }
  }

  // X-CH2-Y

  std::size_t secondary_ch2_sites::size() const { return 6; }

  void secondary_ch2_sites::linearise(uctbx::unit_cell const &unit_cell,
                                      sparse_matrix_type *jacobian_transpose)
  {
    using namespace constants;
    site_parameter *pivot             = (site_parameter *)argument(0),
                   *pivot_neighbour_0 = (site_parameter *)argument(1),
                   *pivot_neighbour_1 = (site_parameter *)argument(2);
    independent_scalar_parameter
    *length = (independent_scalar_parameter *)argument(3);
    angle_starting_tetrahedral
    *h_c_h = (angle_starting_tetrahedral *)argument(4);

    // Local frame
    /* (C, e0, e1) is the bisecting plane of the angle X-C-Y
        with e0 bisecting X-C-Y
     */
    cart_t x_p  = unit_cell.orthogonalize(pivot->value);
    cart_t x_pn_0 = unit_cell.orthogonalize(pivot_neighbour_0->value),
           x_pn_1 = unit_cell.orthogonalize(pivot_neighbour_1->value);
    cart_t u_pn_0 = (x_p - x_pn_0).normalize(),
           u_pn_1 = (x_p - x_pn_1).normalize();
    cart_t e0 = (u_pn_1 + u_pn_0).normalize();
    cart_t e2 = (u_pn_1 - u_pn_0).normalize();
    cart_t e1 = e2.cross(e0);
    double l = length->value, theta = h_c_h->value;

    // Hydrogen sites
    double c = std::cos(theta/2), s = std::sin(theta/2);
    af::tiny<cart_t, 2> u_h(c*e0 + s*e1, c*e0 - s*e1);
    for (int k=0; k<2; ++k) x_h[k] = x_p + l*u_h[k];

    // Derivatives
    if (!jacobian_transpose) return;
    sparse_matrix_type &jt = *jacobian_transpose;
    af::tiny<std::size_t, 2> j_h(index(), index() + 3);

    // Riding
    for (int k=0; k<2; ++k) for (int i=0; i<3; ++i) {
      jt.col(j_h[k] + i) = jt.col(pivot->index() + i);
    }

    // Bond stretching
    if (length->is_variable()) {
      for (int k=0; k<2; ++k) {
        frac_t grad_f = unit_cell.fractionalize(u_h[k]);
        for (int i=0; i<3; ++i) jt(length->index(), j_h[k] + i) = grad_f[i];
      }
    }

    // H-C-H flapping
    if (h_c_h->is_variable()) {
      af::tiny<cart_t, 2> grad_c(l/2*(-s*e0 + c*e1), l/2*(-s*e0 - c*e1));
      for (int k=0; k<2; ++k) {
        frac_t grad_f = unit_cell.fractionalize(grad_c[k]);
        for (int i=0; i<3; ++i) jt(h_c_h->index(), j_h[k] + i) = grad_f[i];
      }
    }
  }

  void secondary_ch2_sites::store(uctbx::unit_cell const &unit_cell) const {
    for (int i=0; i<2; ++i) h[i]->site = unit_cell.fractionalize(x_h[i]);
  }


  /***    H
          |
       X0-C-X1
          |
          X2
   */
  std::size_t tertiary_ch_site::size() const { return 3; }

  void tertiary_ch_site::linearise(uctbx::unit_cell const &unit_cell,
                                   sparse_matrix_type *jacobian_transpose)
  {
    using namespace constants;
    site_parameter *pivot = (site_parameter *)argument(0);
    af::tiny<site_parameter *, 3> pivot_neighbour;
    for (int k=0; k<3; ++k) {
      pivot_neighbour[k] = (site_parameter *)argument(k+1);
    }
    independent_scalar_parameter
    *length = (independent_scalar_parameter *)argument(4);

    // Local frame
    cart_t x_p = unit_cell.orthogonalize(pivot->value);
    af::tiny<cart_t, 3> u_cn; // Directions C->Xi
    for (int k=0; k<3; ++k) {
      cart_t x = unit_cell.orthogonalize(pivot_neighbour[k]->value);
      u_cn[k] = (x_p - x).normalize();
    }
    cart_t u = u_cn[0] - u_cn[1], v = u_cn[1] - u_cn[2];
    cart_t e0 = u.cross(v).normalize();
    if (e0*(u_cn[0] + u_cn[1] + u_cn[2]) < 0) e0 = -e0;
    double l = length->value;

    // Hydrogen site
    x_h = x_p + l*e0;

    // Derivatives
    if (!jacobian_transpose) return;
    sparse_matrix_type &jt = *jacobian_transpose;
    std::size_t j_h = index();

    // Riding
    for (int i=0; i<3; ++i) {
      jt.col(j_h + i) = jt.col(pivot->index() + i);
    }

    // Bond stretching
    if (length->is_variable()) {
      frac_t grad_f = unit_cell.fractionalize(e0);
      for (int i=0; i<3; ++i) jt(length->index(), j_h + i) = grad_f[i];
    }
  }

  void tertiary_ch_site::store(uctbx::unit_cell const &unit_cell) const {
    h->site = unit_cell.fractionalize(x_h);
  }


}}}
