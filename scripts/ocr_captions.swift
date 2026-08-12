import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count == 2 else {
    fputs("usage: ocr_captions.swift <frames_dir>\n", stderr)
    exit(2)
}

let directory = URL(fileURLWithPath: CommandLine.arguments[1])
let files = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
    .filter { ["jpg", "jpeg", "png"].contains($0.pathExtension.lowercased()) }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

for (index, file) in files.enumerated() {
    guard let image = NSImage(contentsOf: file),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["en-US"]
    request.minimumTextHeight = 0.012
    request.regionOfInterest = CGRect(x: 0.02, y: 0.18, width: 0.96, height: 0.56)
    try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])
    let strings = (request.results ?? [])
        .compactMap { $0.topCandidates(1).first?.string }
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
    print(String(format: "%.1f\t%@", Double(index) * 0.5, strings.joined(separator: " | ")))
}
