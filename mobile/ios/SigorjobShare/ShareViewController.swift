import UIKit
import Social
import UniformTypeIdentifiers

final class ShareViewController: SLComposeServiceViewController {
  override func isContentValid() -> Bool {
    return true
  }

  override func didSelectPost() {
    guard let item = extensionContext?.inputItems.first as? NSExtensionItem else {
      finishRequest()
      return
    }

    extractSharedText(from: item) { [weak self] text in
      guard let self else { return }
      guard let text, !text.isEmpty else {
        self.finishRequest()
        return
      }

      let encoded = text.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
      if let url = URL(string: "sigorjob://share?text=\(encoded)") {
        self.extensionContext?.open(url) { _ in
          self.finishRequest()
        }
      } else {
        self.finishRequest()
      }
    }
  }

  override func configurationItems() -> [Any]! {
    return []
  }

  private func finishRequest() {
    extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
  }

  private func extractSharedText(from item: NSExtensionItem, completion: @escaping (String?) -> Void) {
    guard let attachments = item.attachments, !attachments.isEmpty else {
      completion(contentText?.trimmingCharacters(in: .whitespacesAndNewlines))
      return
    }

    for provider in attachments {
      if provider.hasItemConformingToTypeIdentifier(UTType.text.identifier) {
        provider.loadItem(forTypeIdentifier: UTType.text.identifier, options: nil) { value, _ in
          if let text = value as? String {
            completion(text.trimmingCharacters(in: .whitespacesAndNewlines))
            return
          }
          if let url = value as? URL {
            completion(url.absoluteString.trimmingCharacters(in: .whitespacesAndNewlines))
            return
          }
          completion(self.contentText?.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return
      }
    }

    completion(contentText?.trimmingCharacters(in: .whitespacesAndNewlines))
  }
}
