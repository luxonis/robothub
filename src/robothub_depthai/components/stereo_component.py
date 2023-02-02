from typing import Union, Optional

import depthai as dai
import depthai_sdk


class StereoComponent:
    def __init__(self, component: depthai_sdk.components.StereoComponent):
        self.component = component

        self.confidence = None
        self.align = None
        self.median = None
        self.extended = None
        self.subpixel = None
        self.lr_check = None
        self.sigma = None
        self.lr_check_threshold = None

    def config_stereo(self,
                      confidence: Optional[int] = None,
                      align: Union[None, str, dai.CameraBoardSocket] = None,
                      median: Union[None, int, dai.MedianFilter] = None,
                      extended: Optional[bool] = None,
                      subpixel: Optional[bool] = None,
                      lr_check: Optional[bool] = None,
                      sigma: Optional[int] = None,
                      lr_check_threshold: Optional[int] = None,
                      ) -> None:
        """
        Configures StereoDepth modes and options.
        """
        self.component.config_stereo(confidence, align, median, extended, subpixel, lr_check, sigma, lr_check_threshold)

        self.confidence = confidence
        self.align = align
        self.median = median
        self.extended = extended
        self.subpixel = subpixel
        self.lr_check = lr_check
        self.sigma = sigma
        self.lr_check_threshold = lr_check_threshold

    @property
    def out(self):
        return self.component.out
