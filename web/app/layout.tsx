import type {Metadata} from "next";import "./globals.css";import "./brand.css";
export const metadata:Metadata={title:"有温度出品",description:"上传参考声音和文案，自动生成带克隆配音的白板动画视频。",icons:{icon:"/brand-mark.png"}};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="zh-CN"><body>{children}</body></html>}
