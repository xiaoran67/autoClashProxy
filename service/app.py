from flask import Flask
from utils.tools import get_result_file_content
import utils.constants as constants
from utils.config import config_instance

app = Flask(__name__)

@app.route("/m3u")
def show_m3u():
    return get_result_file_content(path=config_instance.final_file, file_type="m3u")

@app.route("/live/m3u")
def show_live_m3u():
    return get_result_file_content(path=constants.live_result_path, file_type="m3u")

@app.route("/ipv4/m3u")
def show_ipv4_m3u():
    return get_result_file_content(path=constants.ipv4_result_path, file_type="m3u")

@app.route("/live/ipv6/m3u")
def show_live_ipv6_m3u():
    return get_result_file_content(path=constants.live_ipv6_result_path, file_type="m3u")

if __name__ == '__main__':
    app.run(debug=True)