import logging as log
import warnings
from abc import abstractmethod, ABC
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Union

import cv2
import depthai as dai
import depthai_sdk.classes.packets as packets
import depthai_sdk.trigger_action
import robothub

from robothub_oak.components.camera import Camera
from robothub_oak.components.neural_network import NeuralNetwork
from robothub_oak.components.stereo import Stereo, DepthQuality, DepthRange
from robothub_oak.hub_camera import HubCamera
from robothub_oak.packets import HubPacket, DetectionPacket, TrackerPacket, DepthPacket, IMUPacket
from robothub_oak.trigger_action import Trigger, Action
from robothub_oak.trigger_action.actions import RecordAction
from robothub_oak.trigger_action.triggers import DetectionTrigger

__all__ = [
    'CreateCameraCommand',
    'CreateNeuralNetworkCommand',
    'CreateStereoCommand',
    'CreateTriggerActionCommand',
    'StreamCommand',
    'CommandHistory'
]


class Command(ABC):
    """
    The Command interface declares a method for executing a command.
    """

    def __init__(self, device: 'Device'):
        self.device = device
        self.hub_camera = None

    @abstractmethod
    def execute(self) -> None:
        pass

    def set_camera(self, hub_camera: HubCamera) -> None:
        self.hub_camera = hub_camera

    def get_component(self):
        return None

    def _packet_callback_wrapper(self, callback: Callable) -> Callable[[HubPacket], None]:
        """
        Wraps the callback to be called with a HubPacket.
        :param callback: The callback to be wrapped.
        :return: The wrapped callback.
        """

        def __determine_packet_type(packet) -> Callable:
            packet_type = type(packet)
            if packet_type is packets.DetectionPacket or packet_type is packets.TwoStagePacket:
                return DetectionPacket
            elif packet_type is packets.TrackerPacket:
                return TrackerPacket
            elif packet_type is packets.DepthPacket:
                return DepthPacket
            elif packet_type is packets.IMUPacket:
                return IMUPacket
            else:
                return HubPacket

        def callback_wrapper(packet):
            return callback(__determine_packet_type(packet)(device=self.device, packet=packet))

        return callback_wrapper


class CreateCameraCommand(Command):
    """
    Creates a new camera component.
    """

    def __init__(self, device: 'Device', camera: Camera) -> None:
        super().__init__(device=device)
        self._camera = camera

    def execute(self) -> None:
        camera_component = self.hub_camera.create_camera(source=self._camera.name,
                                                         resolution=self._camera.resolution,
                                                         fps=self._camera.fps)

        if camera_component.is_color():
            camera_component.config_color_camera(**asdict(self._camera.camera_config))

        for callback in self._camera.callbacks:
            fn = callback['callback']
            output_type = callback['output_type']

            # Check if the output type is valid, if not, throw an error
            if output_type not in self._camera.get_valid_output_types():
                raise ValueError(f'Invalid output type: {output_type}')

            self.hub_camera.callback(getattr(camera_component.out, output_type), self._packet_callback_wrapper(fn), True)

        self._camera.camera_component = camera_component

    def get_component(self) -> Camera:
        return self._camera


class CreateNeuralNetworkCommand(Command):
    """
    Creates a new neural network component.
    """

    def __init__(self, device: 'Device', neural_network: NeuralNetwork) -> None:
        super().__init__(device=device)
        self._neural_network = neural_network

    def execute(self) -> None:
        if isinstance(self._neural_network.input, Camera):
            input_component = self._neural_network.input.camera_component
        elif isinstance(self._neural_network.input, NeuralNetwork):
            input_component = self._neural_network.input.nn_component
        else:
            raise ValueError(f'Invalid input component type: {type(self._neural_network.input)}')

        nn_component = self.hub_camera.create_nn(model=self._neural_network.name,
                                                 input=input_component,
                                                 nn_type=self._neural_network.nn_type,
                                                 tracker=self._neural_network.tracker,
                                                 spatial=self._neural_network.spatial,
                                                 decode_fn=self._neural_network.decode_fn)

        nn_component.config_nn(resize_mode=self._neural_network.nn_config.resize_mode,
                               conf_threshold=self._neural_network.nn_config.conf_threshold)

        for callback in self._neural_network.callbacks:
            fn = callback['callback']
            output_type = callback['output_type']

            # Check if the output type is valid, if not, throw an error
            if output_type not in self._neural_network.get_valid_output_types():
                raise ValueError(f'Invalid output type: {output_type}')

            self.hub_camera.callback(getattr(nn_component.out, output_type), self._packet_callback_wrapper(fn), True)

        self._neural_network.nn_component = nn_component

    def get_component(self) -> NeuralNetwork:
        return self._neural_network


class CreateStereoCommand(Command):
    """
    Creates a new stereo component.
    """

    def __init__(self, device: 'Device', stereo: Stereo) -> None:
        super().__init__(device=device)
        self._stereo = stereo

    def execute(self) -> None:
        left = self._stereo.left_camera.camera_component if self._stereo.left_camera else None
        right = self._stereo.right_camera.camera_component if self._stereo.right_camera else None
        stereo_component = self.hub_camera.create_stereo(resolution=self._stereo.resolution,
                                                         fps=self._stereo.fps,
                                                         left=left,
                                                         right=right)

        # Configure stereo component
        stereo_config = self._stereo.stereo_config
        stereo_quality = stereo_config.depth_quality
        stereo_range = stereo_config.depth_range

        align = None
        if stereo_config.align:
            try:
                align = stereo_config.align.camera_component
            except AttributeError:
                log.debug('An error occurred while trying to access the align component. Disabling alignment.')

        # Prefer Enums over values
        if stereo_quality and (stereo_config.median or stereo_config.lr_check or stereo_config.subpixel):
            warnings.warn(f'DepthQuality.{stereo_quality.name} is set. Median, lr_check and subpixel will be ignored.')

        if stereo_range and stereo_config.extended:
            warnings.warn(f'DepthRange.{stereo_range.name} is set. Extended disparity will be ignored.')

        if stereo_quality:
            median = 5 if stereo_quality is DepthQuality.DEFAULT else None
            lr_check = stereo_quality is not DepthQuality.FAST
            subpixel = stereo_quality is DepthQuality.QUALITY
        else:
            median = stereo_config.median
            lr_check = stereo_config.lr_check
            subpixel = stereo_config.subpixel

        if stereo_range:
            extended_disparity = stereo_range is DepthRange.LONG
        else:
            extended_disparity = stereo_config.extended

        if extended_disparity:  # Cannot use subpixel with extended disparity
            subpixel = False

        stereo_component.config_stereo(align=align,
                                       lr_check=lr_check,
                                       subpixel=subpixel,
                                       median=median,
                                       extended=extended_disparity)
        stereo_component.set_colormap(dai.Colormap.JET)
        self._stereo.stereo_component = stereo_component

    def get_component(self) -> Stereo:
        return self._stereo


class CreateTriggerActionCommand(Command):
    def __init__(self,
                 device: 'Device',
                 trigger: Trigger,
                 action: Union[Action, Callable]):
        super().__init__(device=device)
        self._trigger = trigger
        self._action = action

    def execute(self) -> None:
        trigger = self._convert_trigger()
        action = self._convert_action()

        self.hub_camera.create_trigger(trigger=trigger, action=action)

    def _convert_trigger(self) -> depthai_sdk.trigger_action.Trigger:
        input = self._trigger.component._get_sdk_component()
        cooldown = self._trigger.cooldown
        trigger = None
        if isinstance(self._trigger, Trigger):
            condition = self._packet_callback_wrapper(self._trigger.condition)
            trigger = depthai_sdk.trigger_action.Trigger(input, condition, cooldown)
        elif isinstance(self._trigger, DetectionTrigger):
            min_detections = self._trigger.min_detections
            trigger = depthai_sdk.trigger_action.DetectionTrigger(input, min_detections, cooldown)

        return trigger

    def _convert_action(self) -> depthai_sdk.trigger_action.Action:
        # Convert action to depthai_sdk.trigger_action.Action
        action = self._action if isinstance(self._action, Callable) else None
        if not action:
            action_inputs = [i._get_sdk_component() for i in self._action.inputs] \
                if isinstance(self._action.inputs, list) \
                else self._action.inputs._get_sdk_component()

            if isinstance(self._action, RecordAction):
                action = depthai_sdk.trigger_action.RecordAction(
                    inputs=action_inputs,
                    dir_path=self._action.dir_path,
                    duration_after_trigger=self._action.duration_after_trigger,
                    duration_before_trigger=self._action.duration_before_trigger,
                    on_finish_callback=self.upload_recording_as_event if self._action.upload_as_event else None
                )
            elif isinstance(self._action, Action):
                action = depthai_sdk.trigger_action.Action(action_inputs)

        return action

    def upload_recording_as_event(self, path):
        print('uploading', path)
        threads = []
        video_paths = Path(path).glob('*.mp4')
        for video_path in video_paths:
            with open(str(video_path), 'rb') as f:
                robothub.DETECTIONS.send_video_event(video=f.read(), title='Trigger caused recording')


class StreamCommand(Command):
    """
    Creates a new stream.
    """

    def __init__(self, device: 'Device', command: 'Command') -> None:
        super().__init__(device=device)
        self._command = command

    def execute(self) -> None:
        component = self._command.get_component()

        if isinstance(component, Camera):
            stream_component = component.camera_component
        elif isinstance(component, NeuralNetwork):
            stream_component = component.nn_component
        elif isinstance(component, Stereo):
            stream_component = component.stereo_component
        else:
            raise Exception('Component not supported for streaming, only Camera and NeuralNetwork are supported.')

        self.hub_camera.create_stream(component=stream_component,
                                      unique_key=component.stream_key,
                                      name=component.stream_name)


class CommandHistory:
    """
    The CommandHistory keeps track of the created commands.
    """

    def __init__(self) -> None:
        self._commands = []

    def push(self, command: Command) -> None:
        """
        Adds a command to the history.
        """
        self._commands.append(command)

    def pop(self) -> Command:
        """
        Removes the last command from the history.
        """
        return self._commands.pop()

    def __len__(self) -> int:
        return len(self._commands)

    def __iter__(self):
        return iter(self._commands)
