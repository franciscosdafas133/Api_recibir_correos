import imaplib

mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
mail.login("franciscoluisdelgadosantana@gmail.com", "qsmalnlyxbdgkniq")
print("LOGIN OK")
print("todo es okey")