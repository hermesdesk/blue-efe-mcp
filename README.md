# Blue EFE MCP

**A local MCP server that tells an AI agent when more context is worth its cost.**

Before answering, an agent can ask the user, read a file, search, or verify. Each costs time, tokens or the user's patience. This server keeps an explicit Bayesian belief over the hidden task state and recommends either **one context action** or **acting now**, using the rule from
*Active Inference as Context Acquisition for AI Agents* (Dutta, Ramachandran, Sra, 2026, [arXiv:2608.19202](https://arxiv.org/abs/2608.19202)):

> acquire context only when `R(q) − E[R(q | o, a)] > λ · c(a)`  (Theorem 3.4)

- Exact finite Bayes updates, one-step lookahead, declared loss matrix and costs
- Duplicate/correlated evidence is not counted twice (`group`, `source_ref`, hash)
- Idempotent observations, revision guards, audit trail via `efe_inspect`
- No network, no file access, no paid calls. Stdio only. Works with Claude Desktop, Claude Code and Codex
- 17 tests incl. a real MCP stdio round trip (Windows + Linux)

**What it is not:** a multi-step planner, a calibrated model of your sources, or proof that EFE beats other policies. The numbers are only as good as the likelihoods and losses you supply. In the paper authors' own prompt-optimization data, EFE did not outperform round-robin (194 vs 195 / 200); the value is principled, auditable accounting of when to ask.

Quick start: `python -m venv .venv`, `.venv/bin/pip install -r requirements.txt`, `python configure.py`, then register the generated entry in your MCP client and call `efe_example`.

Tools: `efe_example`, `efe_create`, `efe_plan`, `efe_observe`, `efe_inspect`, `efe_close`. Licensed MIT. Not affiliated with the paper's authors.

---

## Tiếng Việt


**MCP server chạy local cho Codex, Claude Desktop và Claude Code.** Dùng nguyên
core tính toán Blue EFE v0.4.0. Server chọn bước lấy thông tin, cập nhật Bayesian,
tính chi phí và xuất nhật ký. Server không tự đọc vault, tìm web hay gọi model.

Đây là gói đã kiểm tra giao thức stdio bằng MCP client thật. Chưa đăng ký vào
cấu hình Codex/Claude đang dùng, chưa kiểm tra bằng một phiên UI trong hai ứng dụng.
Các file cấu hình được tạo để người dùng ghép thêm, không ghi đè cấu hình hiện có.

## Cài trên Windows

Giải nén vào một thư mục cố định. Mở PowerShell tại thư mục `blue-efe-mcp`:

```powershell
.\setup.ps1 -Python 'C:\duong-dan-Python\python.exe'
```

Nếu `python` trên PATH là Python 3.11+ hoạt động bình thường:

```powershell
.\setup.ps1
```

Script tạo `.venv` riêng, tải các dependencies đã khóa phiên bản và sinh thư mục
`config-generated`. Chỉ bước cài dependencies cần mạng. Server không dùng API key
hay dịch vụ trả phí. Script không tự đăng ký server vào client.

Nếu PowerShell không cho chạy script, dùng các lệnh Python tương đương (không cần
đổi execution policy toàn máy):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe configure.py
```

Máy chỉ có alias Windows Store cần chọn executable Python thật. Trên máy đã tạo
gói này, Python được dùng là runtime đi kèm Codex; không giả định máy khác có cùng
đường dẫn. macOS/Linux dùng `python3 -m venv .venv`, `.venv/bin/python`, rồi cùng
`configure.py`. Linux: 17/17 test qua (xem `verification/LINUX.txt`); macOS chưa kiểm thử.

## Nối Codex

Mở `config-generated/CONNECTION_COMMANDS.txt`; sao chép dòng bắt đầu bằng:

```text
codex mcp add blue-efe -- ...
```

Dòng đã sinh chứa đường dẫn tuyệt đối tới đúng Python trong `.venv` và `launch.py`.
Hoặc ghép phần `config-generated/codex.toml` vào cấu hình MCP hiện có. Giữ các
server khác; nếu đã có entry `blue-efe`, kiểm tra trước khi thay. Kiểm tra bằng
`codex mcp list`, rồi mở phiên Codex mới và yêu cầu gọi `efe_example`.

Định dạng dùng `[mcp_servers.blue-efe]`, `command`, `args`, theo
[tài liệu MCP của Codex](https://developers.openai.com/codex/mcp).
Đã đối chiếu `codex mcp add --help` của CLI local; chưa chạy lệnh đăng ký.

## Nối Claude Desktop

Trong Settings → Developer → Edit Config, ghép **entry `blue-efe` bên trong
`mcpServers`** từ `config-generated/claude-desktop.json` vào file hiện có.
Không thay toàn bộ file nếu đang có server khác. Trên Windows vị trí thông thường
là `%APPDATA%\Claude\claude_desktop_config.json`. Khởi động lại Claude Desktop.
[Hướng dẫn local MCP chính thức](https://modelcontextprotocol.io/docs/develop/connect-local-servers).

## Nối Claude Code

Dùng dòng bắt đầu bằng `claude mcp add` trong `CONNECTION_COMMANDS.txt`, hoặc
ghép entry từ `config-generated/claude-code.json` vào `.mcp.json` của project.
Dòng CLI dùng `--transport stdio --scope user`; cấu hình project chỉ áp dụng cho
project đó. Trong Claude Code dùng `/mcp` để kiểm tra.
[Tài liệu MCP của Claude Code](https://code.claude.com/docs/en/mcp).

Nếu di chuyển thư mục hoặc interpreter, chạy lại `configure.py` và cập nhật
entry của client. Các snippet chỉ có tên server và đường dẫn; không chứa secret.

## Cách dùng trong hội thoại

Yêu cầu thử:

> Gọi efe_example và chạy demo EFE. Tạo phiên từ problem trả về, gọi efe_plan,
> mô phỏng observation=1 cho action read với source_ref=fixture:receipt,
> cập nhật bằng efe_observe rồi gọi efe_plan lần nữa. Nói rõ đây là dữ liệu giả.

Kết quả dự kiến: `read`, lợi ích ròng 0,22; sau quan sát posterior `[0.01,0.99]`,
tổng chi phí 0,02, quyết định cuối `ANSWER:paid`. Đây là phép thử giao tiếp và
toán, không phải bằng chứng độ tin cậy 99% của nguồn đời thật.

Đối với một nhiệm vụ thật, mô tả quyết định, các trạng thái có thể, hậu quả sai,
những nguồn/công cụ được phép và ngân sách. Agent phải tạo mô hình tường minh.
Nếu likelihood chưa đo, dùng `model_status=assumed`, ghi rõ giả định; không gắn
nhãn calibrated cho các con số do model tự đoán. Mọi lần thực thi công cụ ngoài
vẫn theo quyền của host và yêu cầu người dùng.

| Tool | Công việc |
|---|---|
| `efe_example` | Input hoàn chỉnh cho demo, có ghi synthetic |
| `efe_create(problem)` | Tạo phiên, nhận `session_id` và `revision=0` |
| `efe_plan(session_id)` | So lợi ích/chi phí và trả một action hoặc terminal |
| `efe_observe(event)` | Nhận kết quả thật/failure, tính phí một lần, cập nhật |
| `efe_inspect(session_id)` | Xem model, belief, ngân sách, nhật ký để host lưu nếu được phép |
| `efe_close(session_id)` | Xóa phiên khỏi bộ nhớ; lấy nhật ký trước nếu cần giữ |

Ví dụ đối số `efe_observe`, với session ID thực trả về và revision mới nhất:

```json
{
  "event": {
    "session_id": "ID nhận từ efe_create",
    "expected_revision": 0,
    "action_id": "read",
    "event_id": "receipt-001",
    "observation": 1,
    "source_ref": "fixture:receipt"
  }
}
```

`observation` là vị trí bắt đầu từ 0 trong `observation_labels` của action,
không phải điểm confidence. Nếu hành động lỗi, dùng `observation=null` và
`failure="mô tả lỗi"`. Gửi lại cùng event phải giữ nguyên toàn bộ input; server
không tính lại phí hay cập nhật lần hai. Event ID cũ với nội dung khác bị từ chối.

## Giới hạn và nguyên tắc vận hành

- MCP là công cụ để agent gọi; nó không tự ép agent dùng EFE ở mọi lượt chat.
- `risk` mode dùng mức giảm Bayes risk trừ `cost_multiplier * cost`;
  `information` mode dùng thông tin tính bằng nats. Khai báo đơn vị chi phí và
  phép quy đổi; không trộn số token, tiền và thiệt hại tùy ý.
- Nên có terminal `STOP:insufficient_evidence` với loss tường minh. Không có
  ngưỡng “đủ chắc chắn” phổ quát được cài ngầm; terminal phụ thuộc ma trận loss.
- Một bước nhìn trước có thể dừng quá sớm nếu cần cả chuỗi hành động phối hợp.
- `source_ref`, hash và `calibration_refs` ở MCP là **metadata do caller cung cấp**,
  không chứng minh file đã được đọc hay nội dung đúng. Server không kiểm tra hash
  trên đĩa. Adapter shadow của gói v0.4 là thành phần riêng có kiểm tra file nguồn.
- Mô hình `caller_calibrated` cần references nhưng vẫn là tuyên bố của caller;
  server không tự xác thực chất lượng calibration. Không có benchmark thật mới.
- Hành động chung nguồn phải khai báo cùng `group`. Dữ liệu nhận lại có cùng
  source_ref hoặc hash sẽ không được cập nhật Bayes lần nữa, dù lần lấy thừa đó
  vẫn bị tính phí. Tương quan không khai báo có thể khiến posterior sai.
- Bằng chứng xác suất bằng 0 gây `STOP:model_mismatch`, giữ belief cũ và tính
  phí lần lấy đó. Lấy nhật ký, sửa model có giải thích trong phiên mới; không
  tự đặt lại prior rồi tính mọi bằng chứng cũ thành độc lập.
- Chi phí là chi phí **model đã khai báo** cho action, không phải telemetry tiền
  hoặc token thực. Không có cập nhật observation trước khi host nhận kết quả.
- Tối đa 64 phiên, 64 trạng thái, 32 actions và 32 outcomes/action. Updates có
  khóa và revision guard. Các nhóm/bằng chứng đã dùng bị loại khỏi lượt sau.
- Mỗi phiên cần **một host thực hiện tuần tự**. `efe_plan` không giữ chỗ cho một
  hành động; hai caller song song có thể cùng thực hiện bên ngoài rồi một bản cập
  nhật bị từ chối vì stale. Khóa chỉ bảo vệ belief ledger. Ngân sách không phải
  giới hạn cứng cho chi tiêu ngoài server, cũng không phải telemetry thực tế.
- Phiên chỉ ở RAM của một server process. Codex và Claude có process riêng;
  không chia sẻ session. Restart mất session. `efe_inspect` xuất được JSON cho
  host lưu; phiên bản này không có persistent database hay import phục hồi.
- Không mở cổng HTTP, không cần background daemon, không tự đọc file người dùng,
  không trả phí. Cài dependencies và client host là hai phạm vi riêng.

## Kiểm tra và đóng gói

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests gồm chính sách, Bayes, lỗi schema, đồng thời, stale revision, retry,
chi phí failure, evidence trùng, model mismatch, JSON/TOML cấu hình và **client
MCP thật** qua stdio. Windows sandbox của công cụ phát triển có thể chặn async
pipe; phép kiểm tra stdio được chạy ở process local thông thường. Nếu chạy server
trực tiếp thấy nó chờ input, đó là bình thường: stdio cần một MCP client.

MCP SDK 1.26.0 được pin để tránh trộn API v1/v2. `requirements-lock.txt` khóa môi
trường đã test. Bản pydantic-settings hiện dùng có thể phát cảnh báo forward
reference của SDK ra stderr; không ảnh hưởng vòng kiểm tra giao thức đã chạy.
Stdout chỉ dùng cho giao thức. Không dùng log stderr làm bằng chứng có API call.

Wheel dùng qua `pip install blue_efe_mcp-0.1.0-py3-none-any.whl`, sau đó
`python -m blue_efe_mcp` hoặc `blue-efe-mcp`. Các dependencies vẫn phải được cài.
Source ZIP có tests, config generator và setup script. `CORE_PROVENANCE.json`
chứng minh core v0.4 được giữ nguyên; wrapper mới là phần mở rộng của chúng ta.

`plugin.json`/`mcp.json` là descriptor local tùy chọn cho host hỗ trợ Agent Plugins.
Descriptor đi kèm nhắm Windows và yêu cầu đã chạy setup ngay tại plugin root;
không nhúng `.venv` vào ZIP. Không có upload hay xác nhận cài qua Plugin UI.
Đường cài chính đã hướng dẫn là đăng ký MCP trực tiếp bằng cấu hình client.

Nguồn: [paper](https://arxiv.org/pdf/2608.19202v1),
[SDK chính thức đã pin](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0).
MCP không thay đổi giới hạn tái lập paper hoặc nguồn v0.3.0 chưa tìm được.
