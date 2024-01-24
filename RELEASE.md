# How to make release of new RobotHub version
1. First bump up version in https://github.com/luxonis/robothub/blob/main/setup.py and https://github.com/luxonis/robothub/blob/main/src/robothub/__init__.py like this https://github.com/luxonis/robothub/commit/398f3c8fb51de8d1db1d19e4f8f29f1ad3f8aaa1
2. Make a commit to main branch with changed code https://github.com/luxonis/robothub
3. Release new version of robothub here: https://github.com/luxonis/robothub/releases it will automatickly run guthub action for deploy https://github.com/luxonis/robothub/actions/runs/7613204833
4. Then run build and publish images action in github https://github.com/luxonis/robothub-images/actions/runs/7613328981 that will generate robothub-app-v2-dev images
5. Test new robothub-app-v2-dev images
6. After testing make a release in robothub-images https://github.com/luxonis/robothub-images/releases
7. Release will automatickli triger action in github https://github.com/luxonis/robothub-images/actions/runs/7614545382 that will generate new production images robothub-app-v2
8. Change images links in rh examples, template app and any neaded to curent version production images like this https://github.com/luxonis/robothub-examples/commit/4b0af0da8dbab542c306a452ac2c66d2722af45a
9. The end (: