from django.core.mail.backends.console import EmailBackend


class ReadableConsoleEmailBackend(EmailBackend):
    """Console backend that prints the decoded body, not the MIME source.

    Django's console backend prints the raw message. A body line over 76
    characters goes out quoted-printable, so long links wrap with a
    trailing ``=`` and copy from the terminal truncated. Printing
    ``message.body`` keeps every link on one line.
    """

    def write_message(self, message):
        headers = [
            f"From: {message.from_email}",
            f"To: {', '.join(message.to)}",
        ]
        if message.cc:
            headers.append(f"Cc: {', '.join(message.cc)}")
        headers.append(f"Subject: {message.subject}")
        self.stream.write("\n".join(headers) + "\n\n")
        self.stream.write(f"{message.body}\n")
        self.stream.write("-" * 79)
        self.stream.write("\n")
