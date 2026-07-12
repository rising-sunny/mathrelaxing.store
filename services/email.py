import json
import os

import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_ADDRESS = "MathRelaxing <orders@mathrelaxing.store>"

FORMAT_LABELS = {
    "canvas":        "Gallery Canvas — 16×20 in · Hand-stretched cotton-poly canvas · pine frame",
    "framed-poster": "Framed Poster — 16×20 in · 200gsm matte paper · black wood frame · cream mat",
    "acrylic":       "Metal Print — 16×20 in · Glossy aluminum panel · sublimation print",
    "poster":        "Art Print — 16×20 in · Enhanced matte paper · 200gsm",
    "postcard-set":  "Postcard — 4×6 in · Premium glossy cardstock",
}

FORMAT_PRICES = {
    "canvas":        "$90",
    "framed-poster": "$105",
    "acrylic":       "$115",
    "poster":        "$35",
    "postcard-set":  "$12",
}


def _build_html(order, edition: int) -> str:
    fmt_id = getattr(order, "format_id", "canvas") or "canvas"
    fmt_label = FORMAT_LABELS.get(fmt_id, fmt_id)
    price = FORMAT_PRICES.get(fmt_id, "")
    name = (order.customer_name or "").split()[0] or "there"

    shipping = {}
    try:
        shipping = json.loads(order.shipping_address or "{}")
    except Exception:
        pass
    addr_parts = [
        shipping.get("address1", ""),
        shipping.get("city", ""),
        shipping.get("zip", ""),
        shipping.get("country", ""),
    ]
    addr_str = ", ".join(p for p in addr_parts if p)

    cert_url = f"https://mathrelaxing.store/certificate/{order.id}"
    logo_url = "https://mathrelaxing.store/static/img/logo-sm.png"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Order Confirmed — MathRelaxing</title>
</head>
<body style="margin:0;padding:0;background:#f0ede8;font-family:Georgia,'Times New Roman',serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0ede8;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- HEADER -->
  <tr>
    <td style="background:#0d0d0d;border-radius:6px 6px 0 0;padding:36px 48px;text-align:center;">
      <img src="{logo_url}" alt="MathRelaxing" width="96" height="69"
           style="display:block;margin:0 auto 16px;border:0;">
      <p style="margin:0;font-family:Georgia,serif;font-size:11px;letter-spacing:0.18em;
                text-transform:uppercase;color:#c8a96e;">
        Mathematical Art Prints
      </p>
    </td>
  </tr>

  <!-- CONFIRMATION BADGE -->
  <tr>
    <td style="background:#1a1a1a;padding:0;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding:24px 48px;border-bottom:1px solid #2a2a2a;">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="vertical-align:middle;padding-right:14px;">
                  <div style="width:36px;height:36px;border-radius:50%;border:1.5px solid #c8a96e;
                              text-align:center;line-height:36px;font-size:16px;color:#c8a96e;">✓</div>
                </td>
                <td style="vertical-align:middle;">
                  <p style="margin:0;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;
                             color:#c8a96e;font-family:monospace;">Order confirmed</p>
                  <p style="margin:4px 0 0;font-family:Georgia,serif;font-size:22px;
                             font-weight:300;color:#e8e4dc;letter-spacing:0.02em;">
                    Thank you, {name}.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- BODY -->
  <tr>
    <td style="background:#fafaf8;padding:40px 48px;">

      <p style="margin:0 0 28px;font-size:14px;line-height:1.8;color:#444;font-family:Georgia,serif;">
        Your print is now in production through Gelato's global network.
        It will be printed locally near your address and shipped directly to you.
      </p>

      <!-- ORDER DETAILS TABLE -->
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid #ddd;border-radius:4px;margin-bottom:32px;">
        <tr>
          <td style="padding:16px 20px;border-bottom:1px solid #eee;">
            <p style="margin:0;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;
                       color:#999;font-family:monospace;">Product</p>
            <p style="margin:4px 0 0;font-size:14px;color:#1a1a1a;font-family:Georgia,serif;">
              {order.product_slug.replace('-', ' ').title()}
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 20px;border-bottom:1px solid #eee;">
            <p style="margin:0;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;
                       color:#999;font-family:monospace;">Format</p>
            <p style="margin:4px 0 0;font-size:14px;color:#1a1a1a;font-family:Georgia,serif;">
              {fmt_label}
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 20px;border-bottom:1px solid #eee;">
            <p style="margin:0;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;
                       color:#999;font-family:monospace;">Edition</p>
            <p style="margin:4px 0 0;font-size:14px;color:#1a1a1a;font-family:Georgia,serif;">
              #{edition} of a limited series
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 20px;border-bottom:1px solid #eee;">
            <p style="margin:0;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;
                       color:#999;font-family:monospace;">Ships to</p>
            <p style="margin:4px 0 0;font-size:14px;color:#1a1a1a;font-family:Georgia,serif;">
              {addr_str or '—'}
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 20px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <p style="margin:0;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;
                             color:#999;font-family:monospace;">Order</p>
                  <p style="margin:4px 0 0;font-size:14px;color:#1a1a1a;font-family:monospace;">
                    #{order.id}
                  </p>
                </td>
                <td align="right">
                  <p style="margin:0;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;
                             color:#999;font-family:monospace;">Total</p>
                  <p style="margin:4px 0 0;font-size:18px;color:#1a1a1a;
                             font-family:Georgia,serif;font-weight:400;">
                    {price}
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>

      <!-- CERTIFICATE CTA -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
        <tr>
          <td align="center">
            <a href="{cert_url}"
               style="display:inline-block;background:#0d0d0d;color:#c8a96e;
                      text-decoration:none;font-family:monospace;font-size:11px;
                      letter-spacing:0.16em;text-transform:uppercase;
                      padding:14px 32px;border-radius:2px;">
              View Certificate of Authenticity →
            </a>
          </td>
        </tr>
      </table>

      <p style="margin:0;font-size:12px;line-height:1.8;color:#888;font-family:Georgia,serif;">
        You will receive a separate shipping notification once your print leaves the production facility.
        Questions? Reply to this email or visit
        <a href="https://mathrelaxing.store" style="color:#b89558;text-decoration:none;">
          mathrelaxing.store
        </a>.
      </p>

    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="background:#0d0d0d;border-radius:0 0 6px 6px;padding:28px 48px;text-align:center;">
      <p style="margin:0 0 8px;font-family:monospace;font-size:10px;letter-spacing:0.16em;
                text-transform:uppercase;color:#555;">
        MathRelaxing · Mathematical Art Prints
      </p>
      <p style="margin:0;font-size:11px;color:#444;">
        <a href="https://mathrelaxing.store" style="color:#555;text-decoration:none;">
          mathrelaxing.store
        </a>
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>

</body>
</html>"""


async def send_order_confirmation(order, edition: int):
    if not RESEND_API_KEY:
        return

    try:
        html = _build_html(order, edition)
        customer_name = order.customer_name or ""
        first_name = customer_name.split()[0] if customer_name else ""
        subject = f"Your order is confirmed — MathRelaxing #{order.id}"
        if first_name:
            subject = f"{first_name}, your order is confirmed — MathRelaxing #{order.id}"

        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": FROM_ADDRESS,
                    "to": [order.customer_email],
                    "subject": subject,
                    "html": html,
                },
                timeout=15,
            )
    except Exception:
        pass


async def send_digital_purchase_email(purchase, product) -> None:
    """Send download link email after a digital product purchase."""
    if not RESEND_API_KEY:
        return

    name = (purchase.customer_name or "").split()[0] or "there"
    download_url = f"https://mathrelaxing.store/download/{purchase.download_token}"
    product_name = product.name if product else "your purchase"
    is_single = purchase.item_index is not None
    item_label = "Image" if is_single else "Bundle"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Your Download — MathRelaxing</title></head>
<body style="margin:0;padding:0;background:#f0ede8;font-family:Georgia,'Times New Roman',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0ede8;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <tr>
    <td style="background:#0d0d0d;border-radius:6px 6px 0 0;padding:36px 48px;text-align:center;">
      <img src="https://mathrelaxing.store/static/img/logo-sm.png" alt="MathRelaxing"
           width="96" height="69" style="display:block;margin:0 auto 16px;border:0;">
      <p style="margin:0;font-family:Georgia,serif;font-size:11px;letter-spacing:0.18em;
                text-transform:uppercase;color:#c8a96e;">Mathematical Art · Digital</p>
    </td>
  </tr>
  <tr>
    <td style="background:#1a1a1a;padding:24px 48px;border-bottom:1px solid #2a2a2a;">
      <table cellpadding="0" cellspacing="0"><tr>
        <td style="vertical-align:middle;padding-right:14px;">
          <div style="width:36px;height:36px;border-radius:50%;border:1.5px solid #c8a96e;
                      text-align:center;line-height:36px;font-size:16px;color:#c8a96e;">✓</div>
        </td>
        <td style="vertical-align:middle;">
          <p style="margin:0;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;
                     color:#c8a96e;font-family:monospace;">Purchase confirmed</p>
          <p style="margin:4px 0 0;font-family:Georgia,serif;font-size:22px;
                     font-weight:300;color:#e8e4dc;">Thank you, {name}.</p>
        </td>
      </tr></table>
    </td>
  </tr>
  <tr>
    <td style="background:#fafaf8;padding:40px 48px;">
      <p style="margin:0 0 24px;font-size:14px;line-height:1.8;color:#444;">
        Your {item_label.lower()} <strong>{product_name}</strong> is ready for download.
        The link below is valid for up to 3 downloads.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
        <tr><td align="center">
          <a href="{download_url}"
             style="display:inline-block;background:#0d0d0d;color:#c8a96e;
                    text-decoration:none;font-family:monospace;font-size:11px;
                    letter-spacing:0.16em;text-transform:uppercase;
                    padding:14px 36px;border-radius:2px;">
            Download Your {item_label} &rarr;
          </a>
        </td></tr>
      </table>
      <p style="margin:0;font-size:12px;line-height:1.8;color:#888;">
        Questions? Reply to this email or visit
        <a href="https://mathrelaxing.store" style="color:#b89558;">mathrelaxing.store</a>.
      </p>
    </td>
  </tr>
  <tr>
    <td style="background:#0d0d0d;border-radius:0 0 6px 6px;padding:24px 48px;text-align:center;">
      <p style="margin:0;font-family:monospace;font-size:10px;letter-spacing:0.16em;
                text-transform:uppercase;color:#555;">MathRelaxing · mathrelaxing.store</p>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={
                    "from": FROM_ADDRESS,
                    "to": [purchase.customer_email],
                    "subject": f"Your download is ready — {product_name} · MathRelaxing",
                    "html": html,
                },
                timeout=15,
            )
    except Exception:
        pass


async def send_lowpoly_download_email(job) -> None:
    if not RESEND_API_KEY:
        return

    import json as _json
    name = (job.customer_name or "").split()[0] or "there"
    pack_size = getattr(job, "pack_size", 1) or 1
    extra_json = getattr(job, "extra_files_json", None)

    all_pairs = [{"coloring_url": job.coloring_url, "colored_url": job.colored_url}]
    if extra_json:
        try:
            all_pairs += _json.loads(extra_json)
        except Exception:
            pass

    def _page_buttons(pairs):
        rows = ""
        for i, pair in enumerate(pairs):
            label = f"Page {i+1} — " if len(pairs) > 1 else ""
            rows += f"""
        <tr>
          <td align="center" style="padding:6px;">
            <a href="{pair['coloring_url']}"
               style="display:inline-block;background:#0d0d0d;color:#c8a96e;
                      text-decoration:none;font-family:monospace;font-size:12px;
                      letter-spacing:0.14em;text-transform:uppercase;
                      padding:14px 32px;border-radius:2px;">
              {label}Coloring Page (blank + numbers)
            </a>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:6px 6px 16px;">
            <a href="{pair['colored_url']}"
               style="display:inline-block;background:#2d5a3d;color:#e8f4ec;
                      text-decoration:none;font-family:monospace;font-size:12px;
                      letter-spacing:0.14em;text-transform:uppercase;
                      padding:14px 32px;border-radius:2px;">
              {label}Color Reference
            </a>
          </td>
        </tr>"""
        return rows

    page_count_str = "3 Coloring Pages" if pack_size >= 3 else "Your Coloring Page"
    pages_verb = "pages are" if pack_size >= 3 else "page is"

    upsell_block = "" if pack_size >= 3 else """
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f0f6ff;border-radius:6px;margin-top:28px;">
        <tr>
          <td style="padding:20px 24px;">
            <p style="margin:0 0 6px;font-size:13px;font-weight:bold;color:#1a1a1a;
                       font-family:Georgia,serif;">Want more pages?</p>
            <p style="margin:0 0 14px;font-size:12px;color:#555;line-height:1.6;
                       font-family:Georgia,serif;">
              Get 3 color-by-number pages for $6.99 &mdash; save $2 vs buying separately.
              Open the ChatGPT assistant and ask for a 3-page pack.
            </p>
            <a href="https://chatgpt.com/g/color-by-number"
               style="display:inline-block;background:#4f8ef7;color:#fff;
                      text-decoration:none;font-family:monospace;font-size:11px;
                      letter-spacing:0.12em;text-transform:uppercase;
                      padding:12px 24px;border-radius:2px;">
              Open Color-by-Number Assistant &rarr;
            </a>
          </td>
        </tr>
      </table>"""

    page_buttons_html = _page_buttons(all_pairs)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Your Color-by-Number Page</title>
</head>
<body style="margin:0;padding:0;background:#f0ede8;font-family:Georgia,'Times New Roman',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0ede8;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <tr>
    <td style="background:#0d0d0d;border-radius:6px 6px 0 0;padding:36px 48px;text-align:center;">
      <img src="https://mathrelaxing.store/static/img/logo-sm.png" alt="MathRelaxing" width="96" height="69"
           style="display:block;margin:0 auto 16px;border:0;">
      <p style="margin:0;font-family:Georgia,serif;font-size:11px;letter-spacing:0.18em;
                text-transform:uppercase;color:#c8a96e;">MathRelaxing</p>
      <p style="margin:8px 0 0;font-family:Georgia,serif;font-size:22px;font-weight:300;
                color:#e8e4dc;">{page_count_str} Ready!</p>
    </td>
  </tr>
  <tr>
    <td style="background:#fafaf8;padding:40px 48px;">
      <p style="margin:0 0 20px;font-size:15px;line-height:1.8;color:#333;font-family:Georgia,serif;">
        Hi {name},<br><br>
        Your personalized color-by-number {pages_verb} ready.
        Right-click each image below and choose <strong>Save image as</strong> to download it.
      </p>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        {page_buttons_html}
      </table>
      <p style="margin:0 0 8px;font-size:13px;line-height:1.7;color:#666;font-family:Georgia,serif;">
        <strong>How to use:</strong> Print the <em>Coloring Page</em> and keep the
        <em>Color Reference</em> nearby to know which number matches each color.
        Works great with colored pencils, markers, or watercolors.
      </p>
      {upsell_block}
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-top:1px solid #eee;margin-top:28px;">
        <tr>
          <td style="padding:24px 0 0;">
            <p style="margin:0 0 8px;font-size:13px;font-weight:bold;color:#1a1a1a;
                       font-family:Georgia,serif;">Discover more at MathRelaxing</p>
            <p style="margin:0 0 16px;font-size:12px;color:#555;line-height:1.7;
                       font-family:Georgia,serif;">
              At MathRelaxing we turn your photos and mathematics into beautiful art &mdash;
              personalized color-by-number coloring pages, limited-edition mathematical art prints
              for your walls, and more. Come explore!
            </p>
            <a href="https://mathrelaxing.store"
               style="display:inline-block;background:#0d0d0d;color:#c8a96e;
                      text-decoration:none;font-family:monospace;font-size:11px;
                      letter-spacing:0.14em;text-transform:uppercase;
                      padding:12px 24px;border-radius:2px;">
              Visit MathRelaxing &rarr;
            </a>
          </td>
        </tr>
      </table>

      <p style="margin:24px 0 0;font-size:12px;color:#999;font-family:Georgia,serif;">
        Questions? Reply to this email or visit
        <a href="https://mathrelaxing.store" style="color:#b89558;">mathrelaxing.store</a>.
      </p>
    </td>
  </tr>
  <tr>
    <td style="background:#0d0d0d;border-radius:0 0 6px 6px;padding:20px 48px;text-align:center;">
      <p style="margin:0;font-size:10px;color:#444;font-family:monospace;letter-spacing:0.14em;">
        MATHRELAXING &middot; mathrelaxing.store
      </p>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": FROM_ADDRESS,
                    "to":   [job.customer_email],
                    "subject": "Your Color-by-Number Coloring Page — MathRelaxing",
                    "html": html,
                },
                timeout=15,
            )
    except Exception:
        pass


async def send_lowpoly_credit_email(credit) -> None:
    """Email the buyer their Low Poly credit redemption link."""
    if not RESEND_API_KEY:
        return

    name       = (credit.customer_name or "").split()[0] or "there"
    pack_size  = credit.pack_size or 1
    token      = credit.token
    url        = f"https://mathrelaxing.store/lowpoly/credit/{token}"
    credits_label = f"{pack_size} credit{'s' if pack_size > 1 else ''}"
    plural     = "s" if pack_size > 1 else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0d0d0d;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d0d0d;padding:40px 0;">
    <tr><td align="center">
      <table width="540" cellpadding="0" cellspacing="0"
             style="background:#111;border:1px solid #2a2a2a;border-radius:8px;overflow:hidden;max-width:100%;">

        <!-- header -->
        <tr>
          <td align="center" style="padding:36px 40px 24px;border-bottom:1px solid #222;">
            <p style="margin:0 0 8px;font-size:11px;letter-spacing:0.18em;color:#888;
                       font-family:monospace;text-transform:uppercase;">MathRelaxing</p>
            <h1 style="margin:0;font-size:22px;color:#e8e0d4;font-weight:normal;line-height:1.3;">
              Your Low Poly credit{plural} {'are' if pack_size > 1 else 'is'} ready 🎨
            </h1>
          </td>
        </tr>

        <!-- body -->
        <tr>
          <td style="padding:32px 40px;">
            <p style="margin:0 0 16px;font-size:14px;color:#bbb;line-height:1.7;">
              Hi {name},<br><br>
              You purchased <strong style="color:#e8e0d4;">{credits_label}</strong> for the
              Low Poly Color-by-Number generator. Click the button below to upload your
              photo{'s' if pack_size > 1 else ''} and create your coloring page{'s' if pack_size > 1 else ''}.
            </p>

            <!-- CTA -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;">
              <tr>
                <td align="center">
                  <a href="{url}"
                     style="display:inline-block;background:#6c63ff;color:#fff;
                            text-decoration:none;font-family:monospace;font-size:13px;
                            letter-spacing:0.12em;text-transform:uppercase;
                            padding:16px 40px;border-radius:6px;">
                    Use my credit{'s' if pack_size > 1 else ''} →
                  </a>
                </td>
              </tr>
            </table>

            <p style="margin:0 0 8px;font-size:12px;color:#777;line-height:1.6;">
              Or copy this link:
            </p>
            <p style="margin:0 0 24px;font-size:11px;color:#6c63ff;
                       font-family:monospace;word-break:break-all;">
              {url}
            </p>

            <!-- what to expect -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#1a1a1a;border-radius:6px;margin-bottom:24px;">
              <tr>
                <td style="padding:20px 24px;">
                  <p style="margin:0 0 10px;font-size:12px;font-weight:bold;
                             color:#e8e0d4;font-family:monospace;text-transform:uppercase;
                             letter-spacing:0.1em;">What happens next</p>
                  <p style="margin:0;font-size:12px;color:#999;line-height:1.8;">
                    1. Open the link above<br>
                    2. Preview with an example image to choose your style<br>
                    3. Upload your own photo (JPEG or PNG, up to 20 MB)<br>
                    4. Choose colors (8 / 12 / 20) and grid style<br>
                    5. Generate — your files arrive by email instantly
                  </p>
                </td>
              </tr>
            </table>

            <p style="margin:0;font-size:11px;color:#555;line-height:1.6;">
              Each credit = 1 print-ready coloring page (2550&times;3300 px, 300 DPI) +
              color reference sheet. Credits don&rsquo;t expire.
            </p>
          </td>
        </tr>

        <!-- footer -->
        <tr>
          <td align="center" style="padding:20px 40px;border-top:1px solid #1e1e1e;">
            <p style="margin:0;font-size:10px;color:#444;font-family:monospace;">
              mathrelaxing.store &mdash; mathematics made visible
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={
                    "from":    FROM_ADDRESS,
                    "to":      [credit.customer_email],
                    "subject": f"Your Low Poly credit{'s' if pack_size > 1 else ''} — MathRelaxing 🎨",
                    "html":    html,
                },
                timeout=15,
            )
    except Exception:
        pass
