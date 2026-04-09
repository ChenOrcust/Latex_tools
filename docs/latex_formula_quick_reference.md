# LaTeX 公式代码速查

## 基本写法

| 目标 | LaTeX |
|---|---|
| 上标 | `x^2` |
| 下标 | `a_i` |
| 分数 | `\frac{a}{b}` |
| 根号 | `\sqrt{x}` |
| n 次根 | `\sqrt[n]{x}` |
| 空格 | `a\,b`、`a\quad b` |
| 文本 | `\text{其中 } x>0` |

## 常用希腊字母

| 字母 | LaTeX | 字母 | LaTeX |
|---|---|---|---|
| α | `\alpha` | β | `\beta` |
| γ | `\gamma` | Δ | `\Delta` |
| θ | `\theta` | λ | `\lambda` |
| μ | `\mu` | π | `\pi` |
| σ | `\sigma` | Ω | `\Omega` |

## 运算符

| 目标 | LaTeX |
|---|---|
| 求和 | `\sum_{i=1}^{n} i` |
| 连乘 | `\prod_{i=1}^{n} i` |
| 极限 | `\lim_{x\to 0} \frac{\sin x}{x}` |
| 积分 | `\int_a^b f(x)\,dx` |
| 二重积分 | `\iint_D f(x,y)\,dx\,dy` |
| 偏导 | `\frac{\partial f}{\partial x}` |
| 无穷 | `\infty` |
| 正负号 | `\pm` |

## 关系与集合

| 目标 | LaTeX |
|---|---|
| 不等于 | `\ne` |
| 小于等于 | `\le` |
| 大于等于 | `\ge` |
| 约等于 | `\approx` |
| 属于 | `x \in A` |
| 不属于 | `x \notin A` |
| 子集 | `A \subset B` |
| 并集 | `A \cup B` |
| 交集 | `A \cap B` |
| 空集 | `\emptyset` |

## 括号

| 目标 | LaTeX |
|---|---|
| 自动伸缩圆括号 | `\left( \frac{a}{b} \right)` |
| 自动伸缩方括号 | `\left[ x^2 \right]` |
| 自动伸缩花括号 | `\left\{ x \in A \right\}` |
| 绝对值 | `\left| x \right|` |
| 范数 | `\left\| x \right\|` |

## 矩阵

```latex
\begin{matrix}
a & b \\
c & d
\end{matrix}
```

```latex
\begin{pmatrix}
a & b \\
c & d
\end{pmatrix}
```

```latex
\begin{bmatrix}
a & b \\
c & d
\end{bmatrix}
```

## 分段函数

```latex
f(x)=
\begin{cases}
x^2, & x \ge 0 \\
-x, & x < 0
\end{cases}
```

## 多行对齐

```latex
\begin{aligned}
a^2-b^2 &= (a-b)(a+b) \\
(a+b)^2 &= a^2+2ab+b^2
\end{aligned}
```

## 常见函数

| 目标 | LaTeX |
|---|---|
| 正弦 | `\sin x` |
| 余弦 | `\cos x` |
| 正切 | `\tan x` |
| 对数 | `\log x` |
| 自然对数 | `\ln x` |
| 指数 | `e^x` |
| 最大值 | `\max_{x\in A} f(x)` |
| 最小值 | `\min_{x\in A} f(x)` |

## 向量与符号

| 目标 | LaTeX |
|---|---|
| 向量 | `\vec{x}` |
| 粗体向量 | `\mathbf{x}` |
| 横线 | `\bar{x}` |
| 帽子 | `\hat{x}` |
| 点乘 | `a \cdot b` |
| 叉乘 | `a \times b` |
| 省略号 | `x_1, x_2, \ldots, x_n` |

## 小提示

- App 输出框里只需要写公式主体，不需要外层 `$...$`。
- 渲染预览使用 Matplotlib mathtext，常用公式效果较好。
- `aligned`、`cases`、复杂宏包命令可能无法在预览区渲染，但 LaTeX 代码仍可复制到支持完整 LaTeX 的编辑器中使用。

