import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { LiveDataProvider } from "./LiveDataProvider";
import { Nav } from "./Nav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sentinel Enterprise Security",
  description: "Employer-facing security operations console for Sentinel's synthetic defensive lab.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full bg-[#071019] text-slate-100">
        <LiveDataProvider>
          <Nav />
          <div className="min-h-screen lg:pl-[246px]">
            <div className="soc-grid min-h-screen">{children}</div>
          </div>
        </LiveDataProvider>
      </body>
    </html>
  );
}
