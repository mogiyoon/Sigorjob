// Buffer 폴리필 (QR base64 디코딩에 필요)
import { Buffer } from "buffer";
global.Buffer = Buffer;

import { AppRegistry } from "react-native";
import App from "./App";
import { name as appName } from "./app.json";

AppRegistry.registerComponent(appName, () => App);
