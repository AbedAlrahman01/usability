from flight_delay_explorer.renderers import render_map_page
from flight_delay_explorer.ui import configure_page, prepare_repository, render_sidebar_filters


configure_page("Map View")
repository = prepare_repository()
global_filters = render_sidebar_filters(repository)
render_map_page(repository, global_filters)

