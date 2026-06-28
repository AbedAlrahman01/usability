from flight_delay_explorer.renderers import render_comparison_page
from flight_delay_explorer.ui import configure_page, prepare_repository, render_sidebar_filters


configure_page("Comparison Mode")
repository = prepare_repository()
global_filters = render_sidebar_filters(repository)
render_comparison_page(repository, global_filters)

