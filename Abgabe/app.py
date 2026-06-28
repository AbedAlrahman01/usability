from flight_delay_explorer.renderers import render_overview_page
from flight_delay_explorer.ui import configure_page, prepare_repository, render_sidebar_filters


configure_page("Flight Delay Explorer")
repository = prepare_repository()
global_filters = render_sidebar_filters(repository)
render_overview_page(repository, global_filters)

