from uuid import uuid4

__all__ = ['_check_names', '_check_video_format', '_check_frame_format', '_check_file_format', '_check_args', '_check_video_metadata', '_check_frame_metadata']

def _check_names(name, filename, prefix):
    """Checks name and filename, if either is None, creates new ones. If both are None both get the same name."""
    if name == None and filename == None:
        name = f'{prefix}__{str(uuid4())}'
        filename = name
    elif name == None and filename != None:
        name = f'{prefix}__{str(uuid4())}'
    elif filename == None and name != None:
        filename = f'{prefix}__{str(uuid4())}'
    return name, filename

def _check_video_format(video_bytes) -> None:
    """Checks type and format of video."""
    if not isinstance(video_bytes, (bytes, bytearray)):
        raise TypeError(f'"_bytes" argument of add_video() of type "{type(video_bytes)}" needs to be of type "(bytes | bytearray)"')

    # TODO check format of video
    if 0:
        raise RuntimeError(f'"_bytes" argument of add_video() is not a valid allowed video format. If you wish to bypass format checking for videos, send your videos as files instead.')

def _check_frame_format(frame_bytes) -> None:
    """Checks type and format of frame."""
    if not isinstance(frame_bytes, (bytes, bytearray)):
        raise TypeError(f'"_bytes" argument of add_frame() of type "{type(frame_bytes)}" needs to be of type "(bytes | bytearray)"')

    # TODO check format of frame 
    if 0:
        raise RuntimeError(f'"_bytes" argument of add_frame() is not a valid allowed image format. If you wish to bypass format checking for frames, send your frames as files instead.')

def _check_file_format(file_bytes) -> None:
    """Checks type of file."""
    if not isinstance(file_bytes, (bytes, bytearray)):
        raise TypeError(f'"_bytes" argument of add_file() of type "{type(file_bytes)}" needs to be of type "(bytes | bytearray)"')

def _check_args(name, mx_id, filename) -> None:
    """Checks whether Event arguments are valid."""
    if name != None:
        if not isinstance(name, str):
            raise TypeError(f'"name" argument needs to be None or type "str", but is type "{type(name)}"!')
        if len(name) == 0:
            raise RuntimeError(f'"name" argument can\'t be an empty string')
    if mx_id != None:
        if not isinstance(mx_id, str):
            raise TypeError(f'"camera_serial" argument needs to be None or type "str", but is type "{type(mx_id)}"!')
        if len(mx_id) == 0:
            raise RuntimeError(f'"camera_serial" argument can\'t be an empty string')
    if filename != None:
        if not isinstance(filename, str):
            raise TypeError(f'"filename" argument needs to be None or type "str", but is type "{type(filename)}"!')
        if filename == "":
            raise RuntimeError(f'"filename" argument can\'t be an empty string')
        # NOTE Filename checking heuristics could be implemented here so that e.g. creating "/" file is avoided


    ### Metadata checking functions ###

def _check_object_array(object_array: list):
    assert isinstance(object_array, list), "metadata must contain a list of objects for a frame"
    for meta_object in object_array:
        assert isinstance(meta_object, dict), "Each Trail/Text/Detection object must be a dictionary"
        assert 'type' in meta_object.keys(), "Each Trail/Text/Detection object must specify a type"
        if meta_object['type'] == 'detections':
            pass
        elif meta_object['type'] == 'text':
            pass
        elif meta_object['type'] == 'trail':
            pass
        else:
            raise RuntimeError('Invalid object type, valid options are: ["trail", "text", "detections"]')
        if 'children' in meta_object.keys():
            _check_object_array(meta_object['children'])

def _check_metadata_config(config: dict):
    if config.get('img_scale') is not None:
        assert isinstance(config['img_scale'], (float, int)), "Image scale must be float or int"

    if config.get('detection') is not None:
        assert isinstance(config['detection'], dict)
        assert 'thickness' in config['detection'].keys(), 'Detection settings must specify "thickness"'
        assert 'fill_transparency' in config['detection'].keys(), 'Detection settings must specify "fill_transparency"'
        assert 'box_roundness' in config['detection'].keys(), 'Detection settings must specify "box_roundness"'
        assert 'color' in config['detection'].keys(), 'Detection settings must specify "color"'

        assert isinstance(config['detection']['thickness'], (float, int)), '"thickness" must be float or int'
        assert isinstance(config['detection']['fill_transparency'], (float, int)), '"fill_transparency" must be float or int'
        assert isinstance(config['detection']['box_roundness'], (float, int)), '"box_roundness" must be float or int'
        assert isinstance(config['detection']['color'], list), '"color" must be an array of three integers [R, G, B]'
        assert len(config['detection']['color']) == 3, '"color" must be an array of three integers [R, G, B]'
        for color_int in config['detection']['color']:
            assert isinstance(color_int, int), '"color" must be an array of three integers [R, G, B]'
            assert color_int >= 0, 'color must be an integer between (and including) 0 and 255'
            assert color_int <= 255, 'color must be an integer between (and including) 0 and 255'

    if config.get('text') is not None:
        assert isinstance(config['text'], dict)
        assert 'font_color' in config['text'].keys(), 'Text settings must specify "font_color"'
        assert 'font_transparency' in config['text'].keys(), 'Text settings must specify "font_transparency"'
        assert 'font_scale' in config['text'].keys(), 'Text settings must specify "font_scale"'
        assert 'font_thickness' in config['text'].keys(), 'Text settings must specify "font_thickness"'
        assert 'bg_transparency' in config['text'].keys(), 'Text settings must specify "bg_transparency"'
        assert 'bg_color' in config['text'].keys(), 'Text settings must specify "bg_color"'

        assert isinstance(config['text']['font_color'], list), '"font_color" must be an array of three integers [R, G, B]'
        assert isinstance(config['text']['font_transparency'], (float, int)), '"font_transparency" must be float or int'
        assert isinstance(config['text']['font_scale'], (float, int)), '"font_scale" must be float or int'
        assert isinstance(config['text']['font_thickness'], (float, int)), '"font_thickness" must be float or int'
        assert isinstance(config['text']['bg_transparency'], (float, int)), '"bg_transparency" must be float or int'
        assert isinstance(config['text']['bg_color'], list), '"bg_color" must be an array of three integers [R, G, B]'

        for color_int in config['text']['font_color']:
            assert isinstance(color_int, int), '"font_color" must be an array of three integers [R, G, B]'
            assert color_int >= 0, 'color must be an integer between (and including) 0 and 255'
            assert color_int <= 255, 'color must be an integer between (and including) 0 and 255'

        for color_int in config['text']['bg_color']:
            assert isinstance(color_int, int), '"bg_color" must be an array of three integers [R, G, B]'
            assert color_int >= 0, 'color must be an integer between (and including) 0 and 255'
            assert color_int <= 255, 'color must be an integer between (and including) 0 and 255'

    if config.get('tracking') is not None:
        assert isinstance(config['tracking'], dict)
        assert 'line_thickness' in config['tracking'].keys(), 'Tracking settings must specify "line_thickness"'
        assert 'line_color' in config['tracking'].keys(), 'Tracking settings must specify "line_color"'

        assert isinstance(config['tracking']['line_thickness'], (float, int)), '"line_thickness" must be float or int'
        assert isinstance(config['tracking']['line_color'], list), '"line_color" must be an array of three integers [R, G, B]'

        for color_int in config['tracking']['line_color']:
            assert isinstance(color_int, int), '"line_color" must be an array of three integers [R, G, B]'
            assert color_int >= 0, 'color must be an integer between (and including) 0 and 255'
            assert color_int <= 255, 'color must be an integer between (and including) 0 and 255'

def _check_video_metadata(metadata: dict) -> None:
    assert isinstance(metadata, dict), "video metadata must be a dictionary"
    assert 'config' in metadata.keys(), 'video metadata must contain attribute "config"'
    assert 'objects' in metadata.keys(), 'video metadata must contain attribute "objects"'
    assert 'frame_number' in metadata.keys(), 'video metadata must contain attribute "frame_number"'

    assert isinstance(metadata['frame_number'], int), '"frame_number" must be an integer equal to number of frames of the video'
    assert isinstance(metadata['config'], dict), '"config" must be a dictionary'
    assert isinstance(metadata['objects'], list), '"objects" must be list with length equal to number of frames of the video'

    assert len(metadata['objects']) == metadata['frame_number'], '"objects" must be list with length equal to number of frames of the video'

    _check_metadata_config(metadata['config'])
    for frame_object in metadata['objects']:
        _check_object_array(frame_object)

def _check_frame_metadata(metadata: dict) -> None:
    assert isinstance(metadata, dict), "frame metadata must be a dictionary"
    assert 'config' in metadata.keys(), 'frame metadata must contain attribute "config"'
    assert 'objects' in metadata.keys(), 'frame metadata must contain attribute "objects"'

    assert isinstance(metadata['config'], dict), '"config" must be a dictionary'

    _check_metadata_config(metadata['config'])
    _check_object_array(metadata['objects'])
