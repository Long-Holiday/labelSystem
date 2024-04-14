package com.example.labelMark.domain;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Getter;
import lombok.Setter;

/**
 * <p>
 * 
 * </p>
 *
 * @author wh
 * @since 2024-04-12
 */
@Getter
@Setter
@TableName("server")
@ApiModel(value = "Server对象", description = "")
public class Server implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableField("serid")
    private Integer serid;

    @TableField("sername")
    private String sername;

    @TableField("serdesc")
    private String serdesc;

    @TableField("seryear")
    private String seryear;

    @TableField("publisher")
    private String publisher;

    @ApiModelProperty("发布日期")
    @TableField("publishtime")
    private String publishtime;


}
