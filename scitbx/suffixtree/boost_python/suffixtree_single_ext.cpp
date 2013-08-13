#include <boost/python/module.hpp>
#include <boost/python/class.hpp>
#include <boost/python/copy_const_reference.hpp>
#include <boost/python/with_custodian_and_ward.hpp>
#include <boost/python/stl_iterator.hpp>
#include <boost/python/to_python_converter.hpp>

#include <boost/unordered_map.hpp>

#include <boost_adaptbx/boost_range_python.hpp>
#include <scitbx/boost_python/pair_as_tuple.hpp>
#include <scitbx/boost_python/iterator_range.hpp>

#include <scitbx/suffixtree/word.hpp>
#include <scitbx/suffixtree/boost_python/edge_exports.hpp>
#include <scitbx/suffixtree/boost_python/tree_exports.hpp>
#include <scitbx/suffixtree/boost_python/object_extensions.hpp>
#include <scitbx/suffixtree/matching_statistics.hpp>

namespace scitbx
{
namespace suffixtree
{
namespace
{

template< typename Key, typename Value >
class BoostHashMapAdapter
{
public:
  typedef boost::unordered_map< Key, Value > type;
};

template< typename Glyph >
struct python_exports
{
  typedef Glyph glyph_type;
  typedef word::Single< glyph_type > word_type;
  typedef typename word_type::substring_type substring_type;
  typedef typename word_type::index_type index_type;

  typedef std::size_t suffix_label_type;

  template< typename IIterator >
  static boost::python::object get_range(
    typename IIterator::tree_type const& tree,
    boost::python::object const& iterable
    )
  {
    typedef boost::python::stl_input_iterator< typename IIterator::glyph_type > iter_type;

    iter_type begin( iterable );
    iter_type end;

    return scitbx::boost_python::as_iterator(
      IIterator( tree, begin, end),
      IIterator( tree, end, end )
      );
  }

  static void wrap()
  {
    using namespace boost::python;

    boost_adaptbx::python::generic_range_wrapper< substring_type >
      ::wrap( "substring" );

    const glyph_type& (word_type::*pindexing)(const index_type&) const =
      &word_type::operator [];

    class_< word_type >( "word", no_init )
      .def( init<>() )
      .def( "append", &word_type::push_back, arg( "glyph" ) )
      .def( "length", &word_type::length_ptr )
      .def(
        "substring",
        &word_type::substring,
        with_custodian_and_ward_postcall< 0, 1 >(),
        ( arg( "begin" ), arg( "end" ) )
        )
      .def(
        "__getitem__",
        pindexing,
        arg( "index" ),
        return_value_policy< copy_const_reference >()
        )
      ;
    python::edge_exports<
      glyph_type,
      index_type,
      typename word_type::const_length_ptr_type,
      suffix_label_type,
      BoostHashMapAdapter
      >::wrap();
    python::tree_exports< word_type, suffix_label_type, BoostHashMapAdapter >::wrap();
    typedef Tree< word_type, suffix_label_type, BoostHashMapAdapter > tree_type;
    python::ukkonen_builder_exports< tree_type >::wrap();


    typedef MSI< tree_type, stl_input_iterator< glyph_type > > msi_type;

    scitbx::boost_python::export_range_as_iterator< msi_type >(
      "matching_statistics_iterator"
      );

    to_python_converter<
      typename msi_type::position_type,
      scitbx::boost_python::PairToTupleConverter< typename msi_type::position_type >
      >();

    to_python_converter<
      typename msi_type::value_type,
      scitbx::boost_python::PairToTupleConverter< typename msi_type::value_type >
      >();

    def( "matching_statistics", get_range< msi_type >, ( arg( "tree" ), arg( "iterable" ) ) );
  }
};

} // namespace <anonymous>
} // namespace suffixtree
} // namespace scitbx


BOOST_PYTHON_MODULE(scitbx_suffixtree_single_ext)
{
  // single module
  scitbx::suffixtree::python_exports< boost::python::object >::wrap();
}
